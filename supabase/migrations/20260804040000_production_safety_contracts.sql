-- Production safety contracts: deterministic V1 household selection, atomic
-- onboarding, audited transaction voiding, and last-owner protection.

create or replace function public.get_current_household()
returns uuid
language plpgsql
stable
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_count integer;
  v_household_id uuid;
begin
  if auth.uid() is null then
    raise exception 'authentication required' using errcode = '42501';
  end if;

  select count(*), min(hm.household_id::text)::uuid
  into v_count, v_household_id
  from public.household_members hm
  where hm.profile_id = auth.uid()
    and hm.member_type = 'user'
    and hm.is_active;

  if v_count > 1 then
    raise exception 'V1 supports exactly one active household per user'
      using errcode = '21000';
  end if;
  return v_household_id;
end;
$$;

revoke all on function public.get_current_household() from public, anon, service_role;
grant execute on function public.get_current_household() to authenticated;

create or replace function public.setup_household(
  p_display_name text,
  p_household_name text,
  p_members jsonb default '[]'::jsonb,
  p_accounts jsonb default '[]'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_user_id uuid := auth.uid();
  v_household_id uuid;
  v_owner_member_id uuid;
  v_membership_count integer;
  v_created boolean := false;
  v_item jsonb;
  v_name text;
  v_account_type text;
  v_currency text;
  v_opening_balance bigint;
  v_credit_limit bigint;
  v_statement_day smallint;
  v_payment_due_day smallint;
  v_existing_account public.accounts;
begin
  if v_user_id is null then
    raise exception 'authentication required' using errcode = '42501';
  end if;
  if p_display_name is null
     or char_length(trim(p_display_name)) not between 1 and 100 then
    raise exception 'display_name must contain 1-100 characters' using errcode = '22023';
  end if;
  if p_household_name is null
     or char_length(trim(p_household_name)) not between 1 and 100 then
    raise exception 'household_name must contain 1-100 characters' using errcode = '22023';
  end if;
  if p_members is null or jsonb_typeof(p_members) <> 'array'
     or jsonb_array_length(p_members) > 20 then
    raise exception 'members must be a JSON array with at most 20 items'
      using errcode = '22023';
  end if;
  if p_accounts is null or jsonb_typeof(p_accounts) <> 'array'
     or jsonb_array_length(p_accounts) not between 1 and 20 then
    raise exception 'accounts must be a JSON array with 1-20 items'
      using errcode = '22023';
  end if;

  -- Validate the full payload before creating any rows. The function itself is
  -- atomic, but early validation gives stable client-facing errors.
  for v_item in select value from jsonb_array_elements(p_members)
  loop
    if jsonb_typeof(v_item) <> 'object'
       or exists (
         select 1 from jsonb_object_keys(v_item) k(key)
         where k.key <> 'name'
       )
       or jsonb_typeof(v_item -> 'name') is distinct from 'string'
       or char_length(trim(v_item ->> 'name')) not between 1 and 100 then
      raise exception 'each member must be an object containing only name (1-100 characters)'
        using errcode = '22023';
    end if;
  end loop;
  if exists (
    select 1
    from jsonb_array_elements(p_members) m(value)
    group by lower(trim(m.value ->> 'name'))
    having count(*) > 1
  ) then
    raise exception 'member names must be unique' using errcode = '23505';
  end if;

  for v_item in select value from jsonb_array_elements(p_accounts)
  loop
    if jsonb_typeof(v_item) <> 'object'
       or exists (
         select 1 from jsonb_object_keys(v_item) k(key)
         where k.key not in (
           'name', 'account_type', 'currency', 'opening_balance_paise',
           'credit_limit_paise', 'statement_day', 'payment_due_day'
         )
       )
       or jsonb_typeof(v_item -> 'name') is distinct from 'string'
       or char_length(trim(v_item ->> 'name')) not between 1 and 100
       or jsonb_typeof(v_item -> 'account_type') is distinct from 'string'
       or (v_item ->> 'account_type') not in (
         'cash', 'bank', 'wallet', 'credit_card', 'other'
       ) then
      raise exception 'account has an invalid shape, name, or account_type'
        using errcode = '22023';
    end if;
    if v_item ? 'currency'
       and (
         jsonb_typeof(v_item -> 'currency') <> 'string'
         or (v_item ->> 'currency') !~ '^[A-Z]{3}$'
       ) then
      raise exception 'account currency must be an uppercase ISO 4217 code'
        using errcode = '22023';
    end if;
    if v_item ? 'opening_balance_paise'
       and (
         jsonb_typeof(v_item -> 'opening_balance_paise') <> 'number'
         or (v_item ->> 'opening_balance_paise') !~ '^-?[0-9]+$'
       ) then
      raise exception 'opening_balance_paise must be an integer' using errcode = '22023';
    end if;
    if v_item ? 'credit_limit_paise'
       and v_item -> 'credit_limit_paise' <> 'null'::jsonb
       and (
         jsonb_typeof(v_item -> 'credit_limit_paise') <> 'number'
         or (v_item ->> 'credit_limit_paise') !~ '^[0-9]+$'
       ) then
      raise exception 'credit_limit_paise must be a non-negative integer or null'
        using errcode = '22023';
    end if;
    if v_item ? 'statement_day'
       and v_item -> 'statement_day' <> 'null'::jsonb
       and (
         jsonb_typeof(v_item -> 'statement_day') <> 'number'
         or (v_item ->> 'statement_day') !~ '^[0-9]+$'
         or (v_item ->> 'statement_day')::integer not between 1 and 31
       ) then
      raise exception 'statement_day must be an integer from 1 to 31 or null'
        using errcode = '22023';
    end if;
    if v_item ? 'payment_due_day'
       and v_item -> 'payment_due_day' <> 'null'::jsonb
       and (
         jsonb_typeof(v_item -> 'payment_due_day') <> 'number'
         or (v_item ->> 'payment_due_day') !~ '^[0-9]+$'
         or (v_item ->> 'payment_due_day')::integer not between 1 and 31
       ) then
      raise exception 'payment_due_day must be an integer from 1 to 31 or null'
        using errcode = '22023';
    end if;
    if (v_item ->> 'account_type') <> 'credit_card'
       and (
         coalesce(v_item -> 'credit_limit_paise', 'null'::jsonb) <> 'null'::jsonb
         or coalesce(v_item -> 'statement_day', 'null'::jsonb) <> 'null'::jsonb
         or coalesce(v_item -> 'payment_due_day', 'null'::jsonb) <> 'null'::jsonb
       ) then
      raise exception 'credit metadata is valid only for credit_card accounts'
        using errcode = '22023';
    end if;
    if (v_item ->> 'account_type') = 'credit_card'
       and coalesce((v_item ->> 'opening_balance_paise')::bigint, 0) > 0 then
      raise exception 'credit-card outstanding must be a negative opening balance'
        using errcode = '22023';
    end if;
  end loop;
  if exists (
    select 1
    from jsonb_array_elements(p_accounts) a(value)
    group by lower(trim(a.value ->> 'name'))
    having count(*) > 1
  ) then
    raise exception 'account names must be unique' using errcode = '23505';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended('artha:setup:' || v_user_id::text, 0)
  );

  insert into public.profiles (id, display_name)
  values (v_user_id, trim(p_display_name))
  on conflict (id) do update
    set display_name = excluded.display_name;

  select count(*), min(hm.household_id::text)::uuid
  into v_membership_count, v_household_id
  from public.household_members hm
  where hm.profile_id = v_user_id
    and hm.member_type = 'user'
    and hm.is_active;

  if v_membership_count > 1 then
    raise exception 'V1 supports exactly one active household per user'
      using errcode = '21000';
  end if;

  if v_membership_count = 0 then
    insert into public.households (name, created_by)
    values (trim(p_household_name), v_user_id)
    returning id into v_household_id;
    v_created := true;
  else
    if not exists (
      select 1
      from public.households h
      join public.household_members hm on hm.household_id = h.id
      where h.id = v_household_id
        and h.created_by = v_user_id
        and hm.profile_id = v_user_id
        and hm.role = 'owner'
        and hm.is_active
    ) then
      raise exception 'existing V1 household must be owned by the authenticated user'
        using errcode = '42501';
    end if;
    update public.households
    set name = trim(p_household_name)
    where id = v_household_id
      and name is distinct from trim(p_household_name);
  end if;

  select hm.id into strict v_owner_member_id
  from public.household_members hm
  where hm.household_id = v_household_id
    and hm.profile_id = v_user_id
    and hm.role = 'owner'
    and hm.is_active;

  insert into public.categories (household_id, name, category_type, icon)
  select v_household_id, d.name, d.category_type, d.icon
  from (values
    ('Groceries', 'expense', 'shopping-cart'),
    ('Food & Dining', 'expense', 'utensils'),
    ('Housing', 'expense', 'home'),
    ('Transport', 'expense', 'car'),
    ('Shopping', 'expense', 'shopping-bag'),
    ('Health', 'expense', 'heart-pulse'),
    ('Entertainment', 'expense', 'clapperboard'),
    ('Other', 'expense', 'ellipsis'),
    ('Salary', 'income', 'wallet-cards'),
    ('Other Income', 'income', 'circle-plus')
  ) as d(name, category_type, icon)
  where not exists (
    select 1 from public.categories c
    where c.household_id = v_household_id
      and lower(c.name) = lower(d.name)
      and not c.is_archived
  );

  for v_item in select value from jsonb_array_elements(p_members)
  loop
    v_name := trim(v_item ->> 'name');
    if not exists (
      select 1 from public.household_members hm
      where hm.household_id = v_household_id
        and hm.member_type = 'participant'
        and lower(hm.display_name) = lower(v_name)
        and hm.is_active
    ) then
      insert into public.household_members (
        household_id, display_name, member_type, role, is_active
      ) values (
        v_household_id, v_name, 'participant', 'member', true
      );
    end if;
  end loop;

  for v_item in select value from jsonb_array_elements(p_accounts)
  loop
    v_name := trim(v_item ->> 'name');
    v_account_type := v_item ->> 'account_type';
    v_currency := coalesce(v_item ->> 'currency', 'INR');
    v_opening_balance := coalesce((v_item ->> 'opening_balance_paise')::bigint, 0);
    v_credit_limit := (v_item ->> 'credit_limit_paise')::bigint;
    v_statement_day := (v_item ->> 'statement_day')::smallint;
    v_payment_due_day := (v_item ->> 'payment_due_day')::smallint;

    select * into v_existing_account
    from public.accounts a
    where a.household_id = v_household_id
      and lower(a.name) = lower(v_name)
      and not a.is_archived;

    if found then
      if v_existing_account.account_type is distinct from v_account_type
         or v_existing_account.currency is distinct from v_currency
         or v_existing_account.opening_balance_paise is distinct from v_opening_balance
         or v_existing_account.credit_limit_paise is distinct from v_credit_limit
         or v_existing_account.statement_day is distinct from v_statement_day
         or v_existing_account.payment_due_day is distinct from v_payment_due_day then
        raise exception 'existing account % does not match setup payload', v_name
          using errcode = '23505';
      end if;
    else
      insert into public.accounts (
        household_id, name, account_type, currency, opening_balance_paise,
        credit_limit_paise, statement_day, payment_due_day
      ) values (
        v_household_id, v_name, v_account_type, v_currency, v_opening_balance,
        v_credit_limit, v_statement_day, v_payment_due_day
      );
    end if;
  end loop;

  return jsonb_build_object(
    'household_id', v_household_id,
    'owner_member_id', v_owner_member_id,
    'created', v_created,
    'member_ids', (
      select coalesce(jsonb_agg(hm.id order by hm.created_at, hm.id), '[]'::jsonb)
      from public.household_members hm
      where hm.household_id = v_household_id and hm.is_active
    ),
    'account_ids', (
      select coalesce(jsonb_agg(a.id order by a.created_at, a.id), '[]'::jsonb)
      from public.accounts a
      where a.household_id = v_household_id and not a.is_archived
    )
  );
end;
$$;

revoke all on function public.setup_household(text, text, jsonb, jsonb)
  from public, anon, service_role;
grant execute on function public.setup_household(text, text, jsonb, jsonb)
  to authenticated;

create or replace function public.void_transaction(
  p_household_id uuid,
  p_transaction_id uuid,
  p_reason text
)
returns public.transactions
language plpgsql
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_transaction public.transactions;
  v_transfer_link public.transfer_links;
  v_reason text := trim(p_reason);
  v_previous_reason text;
  v_voided_at timestamptz := now();
  v_updated record;
begin
  if auth.uid() is null or not private.is_household_member(p_household_id) then
    raise exception 'not authorized for household' using errcode = '42501';
  end if;
  if p_reason is null or char_length(v_reason) not between 1 and 500 then
    raise exception 'void reason must contain 1-500 characters' using errcode = '22023';
  end if;

  select * into v_transaction
  from public.transactions t
  where t.household_id = p_household_id and t.id = p_transaction_id;
  if not found then
    raise exception 'transaction not found' using errcode = 'P0002';
  end if;

  select * into v_transfer_link
  from public.transfer_links tl
  where tl.household_id = p_household_id
    and (
      tl.transfer_out_transaction_id = p_transaction_id
      or tl.transfer_in_transaction_id = p_transaction_id
    );

  if v_transfer_link.id is not null then
    perform 1
    from public.transactions t
    where t.id in (
      v_transfer_link.transfer_out_transaction_id,
      v_transfer_link.transfer_in_transaction_id
    )
    order by t.id
    for update;
  else
    perform 1
    from public.transactions t
    where t.household_id = p_household_id and t.id = p_transaction_id
    for update;
  end if;

  -- Reload after taking locks so concurrent retries observe the committed state.
  select * into strict v_transaction
  from public.transactions t
  where t.household_id = p_household_id and t.id = p_transaction_id;

  if v_transaction.status = 'voided' then
    select ae.payload ->> 'reason' into v_previous_reason
    from public.audit_events ae
    where ae.household_id = p_household_id
      and ae.entity_type = 'transaction'
      and ae.entity_id = p_transaction_id
      and ae.action = 'voided'
    order by ae.id desc
    limit 1;
    if v_previous_reason is not distinct from v_reason then
      return v_transaction;
    end if;
    raise exception 'transaction was already voided with a different reason'
      using errcode = '23505';
  end if;

  if v_transfer_link.id is not null then

    for v_updated in
      update public.transactions t
      set status = 'voided', voided_at = v_voided_at
      where t.household_id = p_household_id
        and t.id in (
          v_transfer_link.transfer_out_transaction_id,
          v_transfer_link.transfer_in_transaction_id
        )
        and t.status = 'posted'
      returning t.id, t.direction, t.amount_paise
    loop
      insert into public.audit_events (
        household_id, actor_profile_id, entity_type, entity_id, action, payload
      ) values (
        p_household_id,
        auth.uid(),
        'transaction',
        v_updated.id,
        'voided',
        jsonb_build_object(
          'reason', v_reason,
          'direction', v_updated.direction,
          'amount_paise', v_updated.amount_paise,
          'transfer_link_id', v_transfer_link.id
        )
      );
    end loop;
  else
    update public.transactions t
    set status = 'voided', voided_at = v_voided_at
    where t.household_id = p_household_id
      and t.id = p_transaction_id;

    insert into public.audit_events (
      household_id, actor_profile_id, entity_type, entity_id, action, payload
    ) values (
      p_household_id,
      auth.uid(),
      'transaction',
      p_transaction_id,
      'voided',
      jsonb_build_object(
        'reason', v_reason,
        'direction', v_transaction.direction,
        'amount_paise', v_transaction.amount_paise
      )
    );
  end if;

  select * into strict v_transaction
  from public.transactions t
  where t.household_id = p_household_id and t.id = p_transaction_id;
  return v_transaction;
end;
$$;

revoke all on function public.void_transaction(uuid, uuid, text)
  from public, anon, service_role;
grant execute on function public.void_transaction(uuid, uuid, text)
  to authenticated;

create or replace function private.prevent_last_active_owner_removal()
returns trigger
language plpgsql
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_removes_owner boolean;
begin
  if tg_op = 'DELETE' then
    v_removes_owner := old.member_type = 'user'
      and old.role = 'owner'
      and old.is_active;
  else
    v_removes_owner := old.member_type = 'user'
      and old.role = 'owner'
      and old.is_active
      and (
        new.member_type <> 'user'
        or new.role <> 'owner'
        or not new.is_active
        or new.household_id <> old.household_id
      );
  end if;

  if not v_removes_owner then
    if tg_op = 'DELETE' then
      return old;
    end if;
    return new;
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended('artha:owners:' || old.household_id::text, 0)
  );
  if not exists (
    select 1
    from public.household_members hm
    where hm.household_id = old.household_id
      and hm.id <> old.id
      and hm.member_type = 'user'
      and hm.role = 'owner'
      and hm.is_active
  ) then
    raise exception 'cannot remove the final active household owner'
      using errcode = '23514';
  end if;
  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

revoke all on function private.prevent_last_active_owner_removal() from public;

create trigger household_members_preserve_active_owner
before update or delete on public.household_members
for each row execute function private.prevent_last_active_owner_removal();
