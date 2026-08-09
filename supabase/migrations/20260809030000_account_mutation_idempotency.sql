-- Bind every account mutation idempotency key to its exact normalized request.

create index if not exists audit_events_account_idempotency_idx
  on public.audit_events (
    household_id,
    actor_profile_id,
    action,
    ((payload ->> 'idempotency_key'))
  )
  where entity_type = 'account'
    and action in ('created', 'updated', 'archived', 'restored');

create or replace function public.create_managed_account(
  p_household_id uuid,
  p_name text,
  p_account_type text,
  p_opening_balance_paise bigint,
  p_credit_limit_paise bigint,
  p_statement_day smallint,
  p_payment_due_day smallint,
  p_idempotency_key text
)
returns public.accounts
language plpgsql
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_account public.accounts;
  v_event jsonb;
  v_hash text;
begin
  perform private.assert_account_owner(p_household_id);
  if nullif(trim(p_name), '') is null or char_length(trim(p_name)) > 80 then
    raise exception 'account name must be between 1 and 80 characters' using errcode = '22023';
  end if;
  if p_account_type not in ('bank', 'cash', 'wallet', 'credit_card', 'other') then
    raise exception 'invalid account type' using errcode = '22023';
  end if;
  if p_account_type <> 'credit_card' and (
    p_credit_limit_paise is not null or p_statement_day is not null or p_payment_due_day is not null
  ) then
    raise exception 'card details are only valid for credit cards' using errcode = '22023';
  end if;
  if p_account_type = 'credit_card' and p_opening_balance_paise > 0 then
    raise exception 'credit-card outstanding must not be positive' using errcode = '22023';
  end if;
  if p_credit_limit_paise is not null and p_credit_limit_paise < 0 then
    raise exception 'credit limit must not be negative' using errcode = '22023';
  end if;
  if p_statement_day is not null and p_statement_day not between 1 and 31 then
    raise exception 'statement day must be between 1 and 31' using errcode = '22023';
  end if;
  if p_payment_due_day is not null and p_payment_due_day not between 1 and 31 then
    raise exception 'payment due day must be between 1 and 31' using errcode = '22023';
  end if;
  if p_idempotency_key is null
    or char_length(trim(p_idempotency_key)) not between 8 and 200 then
    raise exception 'invalid idempotency key' using errcode = '22023';
  end if;

  v_hash := encode(extensions.digest(convert_to(jsonb_build_object(
    'operation', 'create_managed_account',
    'name', trim(p_name),
    'account_type', p_account_type,
    'opening_balance_paise', p_opening_balance_paise,
    'credit_limit_paise', p_credit_limit_paise,
    'statement_day', p_statement_day,
    'payment_due_day', p_payment_due_day
  )::text, 'utf8'), 'sha256'), 'hex');

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:account:create:' || p_household_id::text || ':' || auth.uid()::text || ':' || trim(p_idempotency_key),
    0
  ));

  select e.payload into v_event
  from public.audit_events e
  where e.household_id = p_household_id
    and e.actor_profile_id = auth.uid()
    and e.entity_type = 'account'
    and e.action = 'created'
    and e.payload ->> 'idempotency_key' = trim(p_idempotency_key)
  order by e.id desc
  limit 1;
  if found then
    if v_event ->> 'request_hash' is distinct from v_hash then
      raise exception 'idempotency key was already used for a different request'
        using errcode = '23505';
    end if;
    select * into strict v_account
    from pg_catalog.jsonb_populate_record(null::public.accounts, v_event -> 'response');
    return v_account;
  end if;

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:account-household:' || p_household_id::text,
    0
  ));
  if (
    select count(*)
    from public.accounts a
    where a.household_id = p_household_id and not a.is_archived
  ) >= 20 then
    raise exception 'active account limit reached' using errcode = '22023';
  end if;

  begin
    insert into public.accounts (
      household_id, name, account_type, opening_balance_paise,
      credit_limit_paise, statement_day, payment_due_day
    ) values (
      p_household_id, trim(p_name), p_account_type, p_opening_balance_paise,
      p_credit_limit_paise, p_statement_day, p_payment_due_day
    ) returning * into v_account;
  exception when unique_violation then
    raise exception 'an active account with this name already exists' using errcode = '23505';
  end;

  insert into public.audit_events (
    household_id, actor_profile_id, entity_type, entity_id, action, payload
  ) values (
    p_household_id,
    auth.uid(),
    'account',
    v_account.id,
    'created',
    jsonb_build_object(
      'idempotency_key', trim(p_idempotency_key),
      'request_hash', v_hash,
      'account_type', p_account_type,
      'response', to_jsonb(v_account)
    )
  );
  return v_account;
end;
$$;

create or replace function public.update_managed_account(
  p_household_id uuid,
  p_account_id uuid,
  p_name text,
  p_credit_limit_paise bigint,
  p_statement_day smallint,
  p_payment_due_day smallint,
  p_idempotency_key text
)
returns public.accounts
language plpgsql
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_account public.accounts;
  v_event jsonb;
  v_hash text;
begin
  perform private.assert_account_owner(p_household_id);
  if nullif(trim(p_name), '') is null or char_length(trim(p_name)) > 80 then
    raise exception 'account name must be between 1 and 80 characters' using errcode = '22023';
  end if;
  if p_idempotency_key is null
    or char_length(trim(p_idempotency_key)) not between 8 and 200 then
    raise exception 'invalid idempotency key' using errcode = '22023';
  end if;

  v_hash := encode(extensions.digest(convert_to(jsonb_build_object(
    'operation', 'update_managed_account',
    'account_id', p_account_id,
    'name', trim(p_name),
    'credit_limit_paise', p_credit_limit_paise,
    'statement_day', p_statement_day,
    'payment_due_day', p_payment_due_day
  )::text, 'utf8'), 'sha256'), 'hex');

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:account:update:' || p_household_id::text || ':' || auth.uid()::text || ':' || trim(p_idempotency_key),
    0
  ));
  select e.payload into v_event
  from public.audit_events e
  where e.household_id = p_household_id
    and e.actor_profile_id = auth.uid()
    and e.entity_type = 'account'
    and e.action = 'updated'
    and e.payload ->> 'idempotency_key' = trim(p_idempotency_key)
  order by e.id desc
  limit 1;
  if found then
    if v_event ->> 'request_hash' is distinct from v_hash then
      raise exception 'idempotency key was already used for a different request'
        using errcode = '23505';
    end if;
    select * into strict v_account
    from pg_catalog.jsonb_populate_record(null::public.accounts, v_event -> 'response');
    return v_account;
  end if;

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:account-row:' || p_account_id::text,
    0
  ));
  select * into v_account
  from public.accounts
  where id = p_account_id and household_id = p_household_id;
  if not found then
    raise exception 'account not found' using errcode = 'P0002';
  end if;
  if v_account.account_type <> 'credit_card' and (
    p_credit_limit_paise is not null or p_statement_day is not null or p_payment_due_day is not null
  ) then
    raise exception 'card details are only valid for credit cards' using errcode = '22023';
  end if;
  if p_credit_limit_paise is not null and p_credit_limit_paise < 0 then
    raise exception 'credit limit must not be negative' using errcode = '22023';
  end if;
  if p_statement_day is not null and p_statement_day not between 1 and 31 then
    raise exception 'statement day must be between 1 and 31' using errcode = '22023';
  end if;
  if p_payment_due_day is not null and p_payment_due_day not between 1 and 31 then
    raise exception 'payment due day must be between 1 and 31' using errcode = '22023';
  end if;

  begin
    update public.accounts set
      name = trim(p_name),
      credit_limit_paise = p_credit_limit_paise,
      statement_day = p_statement_day,
      payment_due_day = p_payment_due_day
    where id = p_account_id and household_id = p_household_id
    returning * into v_account;
  exception when unique_violation then
    raise exception 'an active account with this name already exists' using errcode = '23505';
  end;

  insert into public.audit_events (
    household_id, actor_profile_id, entity_type, entity_id, action, payload
  ) values (
    p_household_id,
    auth.uid(),
    'account',
    v_account.id,
    'updated',
    jsonb_build_object(
      'idempotency_key', trim(p_idempotency_key),
      'request_hash', v_hash,
      'name', v_account.name,
      'response', to_jsonb(v_account)
    )
  );
  return v_account;
end;
$$;

create or replace function public.set_managed_account_archived(
  p_household_id uuid,
  p_account_id uuid,
  p_archived boolean,
  p_idempotency_key text
)
returns public.accounts
language plpgsql
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_account public.accounts;
  v_balance bigint;
  v_event jsonb;
  v_hash text;
begin
  perform private.assert_account_owner(p_household_id);
  if p_archived is null then
    raise exception 'archived state is required' using errcode = '22023';
  end if;
  if p_idempotency_key is null
    or char_length(trim(p_idempotency_key)) not between 8 and 200 then
    raise exception 'invalid idempotency key' using errcode = '22023';
  end if;

  v_hash := encode(extensions.digest(convert_to(jsonb_build_object(
    'operation', 'set_managed_account_archived',
    'account_id', p_account_id,
    'archived', p_archived
  )::text, 'utf8'), 'sha256'), 'hex');

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:account:archive:' || p_household_id::text || ':' || auth.uid()::text || ':' || trim(p_idempotency_key),
    0
  ));
  select e.payload into v_event
  from public.audit_events e
  where e.household_id = p_household_id
    and e.actor_profile_id = auth.uid()
    and e.entity_type = 'account'
    and e.action in ('archived', 'restored')
    and e.payload ->> 'idempotency_key' = trim(p_idempotency_key)
  order by e.id desc
  limit 1;
  if found then
    if v_event ->> 'request_hash' is distinct from v_hash then
      raise exception 'idempotency key was already used for a different request'
        using errcode = '23505';
    end if;
    select * into strict v_account
    from pg_catalog.jsonb_populate_record(null::public.accounts, v_event -> 'response');
    return v_account;
  end if;

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:account-household:' || p_household_id::text,
    0
  ));
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:account-row:' || p_account_id::text,
    0
  ));
  select * into v_account
  from public.accounts
  where id = p_account_id and household_id = p_household_id;
  if not found then
    raise exception 'account not found' using errcode = 'P0002';
  end if;
  if not p_archived and v_account.is_archived and (
    select count(*)
    from public.accounts a
    where a.household_id = p_household_id and not a.is_archived
  ) >= 20 then
    raise exception 'active account limit reached' using errcode = '22023';
  end if;
  if p_archived then
    select b.balance_paise into strict v_balance
    from public.get_account_balances(p_household_id) b
    where b.account_id = p_account_id;
    if v_balance <> 0 then
      raise exception 'only a zero-balance account can be archived' using errcode = '22023';
    end if;
    if (
      select count(*)
      from public.accounts a
      where a.household_id = p_household_id and not a.is_archived
    ) <= 1 then
      raise exception 'the last active account cannot be archived' using errcode = '22023';
    end if;
  end if;

  begin
    update public.accounts
    set is_archived = p_archived
    where id = p_account_id and household_id = p_household_id
    returning * into v_account;
  exception when unique_violation then
    raise exception 'an active account with this name already exists' using errcode = '23505';
  end;

  insert into public.audit_events (
    household_id, actor_profile_id, entity_type, entity_id, action, payload
  ) values (
    p_household_id,
    auth.uid(),
    'account',
    v_account.id,
    case when p_archived then 'archived' else 'restored' end,
    jsonb_build_object(
      'idempotency_key', trim(p_idempotency_key),
      'request_hash', v_hash,
      'response', to_jsonb(v_account)
    )
  );
  return v_account;
end;
$$;

create or replace function public.create_balance_adjustment(
  p_household_id uuid,
  p_account_id uuid,
  p_actual_balance_paise bigint,
  p_reason text,
  p_occurred_at timestamptz,
  p_idempotency_key text
)
returns public.transactions
language plpgsql
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_current bigint;
  v_delta bigint;
  v_transaction public.transactions;
  v_hash text;
  v_currency text;
begin
  perform private.assert_account_owner(p_household_id);
  if nullif(trim(p_reason), '') is null or char_length(trim(p_reason)) > 240 then
    raise exception 'reason must be between 1 and 240 characters' using errcode = '22023';
  end if;
  if p_occurred_at is null or p_occurred_at > now() + interval '5 minutes' then
    raise exception 'invalid adjustment date' using errcode = '22023';
  end if;
  if p_idempotency_key is null
    or char_length(trim(p_idempotency_key)) not between 8 and 200 then
    raise exception 'invalid idempotency key' using errcode = '22023';
  end if;

  v_hash := encode(extensions.digest(convert_to(jsonb_build_object(
    'account_id', p_account_id,
    'actual_balance_paise', p_actual_balance_paise,
    'reason', trim(p_reason),
    'occurred_at', p_occurred_at
  )::text, 'utf8'), 'sha256'), 'hex');

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended('artha:account-row:' || p_account_id::text, 0)
  );

  select * into v_transaction
  from public.transactions
  where household_id = p_household_id
    and created_by = auth.uid()
    and idempotency_key = trim(p_idempotency_key);
  if found then
    if v_transaction.request_hash is distinct from v_hash then
      raise exception 'idempotency key was already used for a different request'
        using errcode = '23505';
    end if;
    return v_transaction;
  end if;

  select a.currency into v_currency
  from public.accounts a
  where a.id = p_account_id
    and a.household_id = p_household_id
    and not a.is_archived;
  if not found then
    raise exception 'active account not found' using errcode = 'P0002';
  end if;

  select b.balance_paise into strict v_current
  from public.get_account_balances(p_household_id) b
  where b.account_id = p_account_id;
  v_delta := p_actual_balance_paise - v_current;
  if v_delta = 0 then
    raise exception 'account already has this balance' using errcode = '22023';
  end if;

  insert into public.transactions (
    household_id, account_id, direction, amount_paise, currency, occurred_at,
    note, idempotency_key, request_hash, metadata, created_by
  ) values (
    p_household_id,
    p_account_id,
    case when v_delta > 0 then 'adjustment_in' else 'adjustment_out' end,
    abs(v_delta),
    v_currency,
    p_occurred_at,
    trim(p_reason),
    trim(p_idempotency_key),
    v_hash,
    jsonb_build_object('actual_balance_paise', p_actual_balance_paise),
    auth.uid()
  ) returning * into v_transaction;

  insert into public.audit_events (
    household_id, actor_profile_id, entity_type, entity_id, action, payload
  ) values (
    p_household_id,
    auth.uid(),
    'transaction',
    v_transaction.id,
    'balance_adjusted',
    jsonb_build_object(
      'account_id', p_account_id,
      'delta_paise', v_delta,
      'request_hash', v_hash
    )
  );
  return v_transaction;
end;
$$;

revoke all on function public.create_managed_account(
  uuid, text, text, bigint, bigint, smallint, smallint, text
) from public, anon, service_role;
revoke all on function public.update_managed_account(
  uuid, uuid, text, bigint, smallint, smallint, text
) from public, anon, service_role;
revoke all on function public.set_managed_account_archived(
  uuid, uuid, boolean, text
) from public, anon, service_role;
revoke all on function public.create_balance_adjustment(
  uuid, uuid, bigint, text, timestamptz, text
) from public, anon, service_role;
grant execute on function public.create_managed_account(
  uuid, text, text, bigint, bigint, smallint, smallint, text
) to authenticated;
grant execute on function public.update_managed_account(
  uuid, uuid, text, bigint, smallint, smallint, text
) to authenticated;
grant execute on function public.set_managed_account_archived(
  uuid, uuid, boolean, text
) to authenticated;
grant execute on function public.create_balance_adjustment(
  uuid, uuid, bigint, text, timestamptz, text
) to authenticated;

notify pgrst, 'reload schema';
