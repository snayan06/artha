-- Daily-use transaction correction foundation. Corrections preserve history by
-- voiding the original row and posting a replacement inside one transaction.

create table private.transaction_correction_requests (
  household_id uuid not null references public.households (id) on delete cascade,
  actor_profile_id uuid not null references public.profiles (id) on delete cascade,
  idempotency_key text not null,
  request_hash text not null check (char_length(request_hash) = 64),
  original_transaction_id uuid not null,
  replacement_transaction_id uuid not null,
  response jsonb not null check (jsonb_typeof(response) = 'object'),
  created_at timestamptz not null default now(),
  primary key (household_id, actor_profile_id, idempotency_key),
  constraint transaction_correction_original_fk
    foreign key (household_id, original_transaction_id)
    references public.transactions (household_id, id) on delete restrict,
  constraint transaction_correction_replacement_fk
    foreign key (household_id, replacement_transaction_id)
    references public.transactions (household_id, id) on delete restrict
);

revoke all on table private.transaction_correction_requests
  from public, anon, authenticated, service_role;

create table private.member_settlement_requests (
  household_id uuid not null references public.households (id) on delete cascade,
  actor_profile_id uuid not null references public.profiles (id) on delete cascade,
  idempotency_key text not null,
  request_hash text not null check (char_length(request_hash) = 64),
  settlement_id uuid not null,
  response jsonb not null check (jsonb_typeof(response) = 'object'),
  created_at timestamptz not null default now(),
  primary key (household_id, actor_profile_id, idempotency_key),
  constraint member_settlement_request_settlement_fk
    foreign key (settlement_id)
    references public.settlements (id) on delete restrict
);

revoke all on table private.member_settlement_requests
  from public, anon, authenticated, service_role;

create function public.get_member_balances(p_household_id uuid)
returns table (member_id uuid, balance_paise bigint)
language sql
stable
security definer
set search_path = ''
set row_security = off
as $$
  with owner_member as (
    select hm.id
    from public.household_members hm
    where hm.household_id = p_household_id
      and hm.profile_id = auth.uid()
      and hm.role = 'owner'
      and hm.is_active
  ),
  balance_deltas as (
    select ts.member_id, ts.amount_paise::bigint as amount_paise
    from public.transactions t
    join owner_member owner on owner.id = t.paid_by_member_id
    join public.transaction_splits ts
      on ts.household_id = t.household_id and ts.transaction_id = t.id
    where t.household_id = p_household_id
      and t.status = 'posted'
      and t.direction = 'expense'
      and ts.member_id <> owner.id

    union all

    select t.paid_by_member_id as member_id, (-ts.amount_paise)::bigint
    from public.transactions t
    join owner_member owner on true
    join public.transaction_splits ts
      on ts.household_id = t.household_id
      and ts.transaction_id = t.id
      and ts.member_id = owner.id
    where t.household_id = p_household_id
      and t.status = 'posted'
      and t.direction = 'expense'
      and t.paid_by_member_id <> owner.id

    union all

    select
      case
        when s.payer_member_id = owner.id then s.payee_member_id
        else s.payer_member_id
      end as member_id,
      case
        when s.payer_member_id = owner.id then s.amount_paise
        else -s.amount_paise
      end::bigint as amount_paise
    from public.settlements s
    join owner_member owner
      on owner.id in (s.payer_member_id, s.payee_member_id)
    join public.transactions movement
      on movement.household_id = s.household_id
      and movement.id = s.transaction_id
      and movement.status = 'posted'
    where s.household_id = p_household_id
  )
  select d.member_id, sum(d.amount_paise)::bigint as balance_paise
  from balance_deltas d
  group by d.member_id
  having sum(d.amount_paise) <> 0
  order by d.member_id;
$$;

revoke all on function public.get_member_balances(uuid)
  from public, anon, service_role;
grant execute on function public.get_member_balances(uuid)
  to authenticated;

create or replace function public.create_settlement(
  p_household_id uuid,
  p_payer_member_id uuid,
  p_payee_member_id uuid,
  p_account_id uuid,
  p_account_direction text,
  p_amount_paise bigint,
  p_currency text,
  p_settled_at timestamptz,
  p_idempotency_key text,
  p_note text default null
)
returns public.settlements
language plpgsql
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_settlement public.settlements;
  v_request_hash text;
  v_owner_member_id uuid;
  v_other_member_id uuid;
  v_balance_paise bigint;
begin
  if auth.uid() is null or not private.is_household_owner(p_household_id) then
    raise exception 'not authorized for household' using errcode = '42501';
  end if;
  if p_idempotency_key is null
    or char_length(trim(p_idempotency_key)) not between 8 and 160 then
    raise exception 'idempotency_key is required (8-160 characters)'
      using errcode = '22023';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    p_household_id::text || ':' || auth.uid()::text || ':settlement:' || trim(p_idempotency_key),
    0
  ));
  select * into v_settlement
  from public.settlements s
  where s.household_id = p_household_id
    and s.created_by = auth.uid()
    and s.idempotency_key = trim(p_idempotency_key);
  if found then
    v_request_hash := encode(extensions.digest(convert_to(jsonb_build_object(
      'household_id', p_household_id,
      'payer_member_id', p_payer_member_id,
      'payee_member_id', p_payee_member_id,
      'account_id', p_account_id,
      'account_direction', p_account_direction,
      'amount_paise', p_amount_paise,
      'currency', p_currency,
      'settled_at', p_settled_at,
      'note', p_note
    )::text, 'UTF8'), 'sha256'), 'hex');
    if v_settlement.request_hash is distinct from v_request_hash then
      raise exception 'idempotency key was already used with a different request'
        using errcode = '23505';
    end if;
    return v_settlement;
  end if;

  select hm.id into strict v_owner_member_id
  from public.household_members hm
  where hm.household_id = p_household_id
    and hm.profile_id = auth.uid()
    and hm.role = 'owner'
    and hm.is_active;
  if p_payer_member_id = v_owner_member_id then
    v_other_member_id := p_payee_member_id;
  elsif p_payee_member_id = v_owner_member_id then
    v_other_member_id := p_payer_member_id;
  else
    raise exception 'settlement must involve the household owner'
      using errcode = '23514';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:member-balance:' || p_household_id::text || ':' || v_other_member_id::text,
    0
  ));
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:account-row:' || p_account_id::text,
    0
  ));
  -- Settlement is rare and correctness-sensitive. This short-lived lock makes
  -- the aggregate plus insert atomic against every transaction/settlement write,
  -- including corrections that can change a participant balance.
  lock table public.transactions in share row exclusive mode;
  lock table public.settlements in share row exclusive mode;

  select b.balance_paise into v_balance_paise
  from public.get_member_balances(p_household_id) b
  where b.member_id = v_other_member_id;
  v_balance_paise := coalesce(v_balance_paise, 0);
  if v_balance_paise = 0 then
    raise exception 'member is already settled up' using errcode = '23514';
  end if;
  if p_amount_paise is null or p_amount_paise <= 0
    or p_amount_paise > abs(v_balance_paise) then
    raise exception 'settlement exceeds the current shared balance'
      using errcode = '23514';
  end if;
  if (
    v_balance_paise > 0
    and (
      p_payer_member_id <> v_other_member_id
      or p_payee_member_id <> v_owner_member_id
      or p_account_direction <> 'settlement_in'
    )
  ) or (
    v_balance_paise < 0
    and (
      p_payer_member_id <> v_owner_member_id
      or p_payee_member_id <> v_other_member_id
      or p_account_direction <> 'settlement_out'
    )
  ) then
    raise exception 'settlement direction does not match the current shared balance'
      using errcode = '23514';
  end if;

  select * into strict v_settlement
  from private.create_settlement_unlocked(
    p_household_id,
    p_payer_member_id,
    p_payee_member_id,
    p_account_id,
    p_account_direction,
    p_amount_paise,
    p_currency,
    p_settled_at,
    p_idempotency_key,
    p_note
  );
  return v_settlement;
end;
$$;

create function public.settle_member_balance(
  p_household_id uuid,
  p_member_id uuid,
  p_account_id uuid,
  p_amount_paise bigint,
  p_settled_at timestamptz,
  p_idempotency_key text,
  p_note text default null
)
returns jsonb
language plpgsql
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_actor uuid := auth.uid();
  v_key text := trim(p_idempotency_key);
  v_note text := nullif(trim(p_note), '');
  v_request_hash text;
  v_existing private.member_settlement_requests;
  v_owner_member_id uuid;
  v_balance_paise bigint;
  v_payer_member_id uuid;
  v_payee_member_id uuid;
  v_account_direction text;
  v_settlement public.settlements;
  v_internal_key text;
  v_response jsonb;
begin
  if v_actor is null or not private.is_household_owner(p_household_id) then
    raise exception 'not authorized for household' using errcode = '42501';
  end if;
  if p_idempotency_key is null or char_length(v_key) not between 8 and 160 then
    raise exception 'idempotency_key is required (8-160 characters)'
      using errcode = '22023';
  end if;
  if p_amount_paise is null or p_amount_paise <= 0 then
    raise exception 'amount_paise must be positive' using errcode = '22023';
  end if;
  if p_settled_at is null then
    raise exception 'settled_at is required' using errcode = '22023';
  end if;
  if p_note is not null and char_length(v_note) > 500 then
    raise exception 'note must contain at most 500 characters' using errcode = '22023';
  end if;

  v_request_hash := encode(extensions.digest(convert_to(jsonb_build_object(
    'household_id', p_household_id,
    'member_id', p_member_id,
    'account_id', p_account_id,
    'amount_paise', p_amount_paise,
    'settled_at', p_settled_at,
    'note', v_note
  )::text, 'UTF8'), 'sha256'), 'hex');
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    p_household_id::text || ':' || v_actor::text || ':member-settlement:' || v_key,
    0
  ));
  select * into v_existing
  from private.member_settlement_requests r
  where r.household_id = p_household_id
    and r.actor_profile_id = v_actor
    and r.idempotency_key = v_key;
  if found then
    if v_existing.request_hash is distinct from v_request_hash then
      raise exception 'idempotency key was already used with a different request'
        using errcode = '23505';
    end if;
    return v_existing.response;
  end if;

  select hm.id into strict v_owner_member_id
  from public.household_members hm
  where hm.household_id = p_household_id
    and hm.profile_id = v_actor
    and hm.role = 'owner'
    and hm.is_active;
  if p_member_id = v_owner_member_id or not exists (
    select 1 from public.household_members hm
    where hm.household_id = p_household_id
      and hm.id = p_member_id
      and hm.is_active
  ) then
    raise exception 'choose an active non-owner household member'
      using errcode = '23514';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:member-balance:' || p_household_id::text || ':' || p_member_id::text,
    0
  ));
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:account-row:' || p_account_id::text,
    0
  ));
  lock table public.transactions in share row exclusive mode;
  lock table public.settlements in share row exclusive mode;

  select b.balance_paise into v_balance_paise
  from public.get_member_balances(p_household_id) b
  where b.member_id = p_member_id;
  v_balance_paise := coalesce(v_balance_paise, 0);
  if v_balance_paise = 0 then
    raise exception 'member is already settled up' using errcode = '23514';
  end if;
  if p_amount_paise > abs(v_balance_paise) then
    raise exception 'settlement exceeds the current shared balance'
      using errcode = '23514';
  end if;
  if v_balance_paise > 0 then
    v_payer_member_id := p_member_id;
    v_payee_member_id := v_owner_member_id;
    v_account_direction := 'settlement_in';
  else
    v_payer_member_id := v_owner_member_id;
    v_payee_member_id := p_member_id;
    v_account_direction := 'settlement_out';
  end if;

  v_internal_key := 'member-settlement-' || encode(extensions.digest(
    convert_to(p_household_id::text || ':' || v_actor::text || ':' || v_key, 'UTF8'),
    'sha256'
  ), 'hex');
  select * into strict v_settlement
  from private.create_settlement_unlocked(
    p_household_id,
    v_payer_member_id,
    v_payee_member_id,
    p_account_id,
    v_account_direction,
    p_amount_paise,
    'INR',
    p_settled_at,
    v_internal_key,
    v_note
  );
  v_response := jsonb_build_object(
    'id', v_settlement.id,
    'transaction_id', v_settlement.transaction_id,
    'member_id', p_member_id,
    'amount_paise', p_amount_paise,
    'balance_paise', case
      when v_balance_paise > 0 then v_balance_paise - p_amount_paise
      else v_balance_paise + p_amount_paise
    end
  );
  insert into private.member_settlement_requests (
    household_id, actor_profile_id, idempotency_key,
    request_hash, settlement_id, response
  ) values (
    p_household_id, v_actor, v_key,
    v_request_hash, v_settlement.id, v_response
  );
  return v_response;
end;
$$;

revoke all on function public.settle_member_balance(
  uuid, uuid, uuid, bigint, timestamptz, text, text
) from public, anon, service_role;
grant execute on function public.settle_member_balance(
  uuid, uuid, uuid, bigint, timestamptz, text, text
) to authenticated;

create function public.replace_transaction(
  p_household_id uuid,
  p_transaction_id uuid,
  p_replacement jsonb,
  p_reason text,
  p_idempotency_key text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_actor uuid := auth.uid();
  v_reason text := trim(p_reason);
  v_key text := trim(p_idempotency_key);
  v_request_hash text;
  v_existing private.transaction_correction_requests;
  v_original public.transactions;
  v_original_link public.transfer_links;
  v_replacement public.transactions;
  v_account_id uuid;
  v_source_account_id uuid;
  v_destination_account_id uuid;
  v_category_id uuid;
  v_category_ids uuid[];
  v_category_name text;
  v_paid_by_member_id uuid;
  v_amount_paise bigint;
  v_currency text;
  v_occurred_at timestamptz;
  v_splits jsonb;
  v_merchant text;
  v_note text;
  v_metadata jsonb;
  v_kind text;
  v_confirm_key text;
  v_response jsonb;
  v_lock_account uuid;
  v_new_transfer record;
  v_replacement_row_id uuid;
  v_activity_id uuid;
begin
  if v_actor is null or not private.is_household_owner(p_household_id) then
    raise exception 'not authorized for household' using errcode = '42501';
  end if;
  if p_idempotency_key is null or char_length(v_key) not between 8 and 160 then
    raise exception 'idempotency_key is required (8-160 characters)'
      using errcode = '22023';
  end if;
  if p_reason is null or char_length(v_reason) not between 1 and 500 then
    raise exception 'correction reason must contain 1-500 characters'
      using errcode = '22023';
  end if;
  if p_replacement is null or jsonb_typeof(p_replacement) <> 'object' then
    raise exception 'replacement must be an object' using errcode = '22023';
  end if;

  v_request_hash := encode(extensions.digest(convert_to(jsonb_build_object(
    'household_id', p_household_id,
    'transaction_id', p_transaction_id,
    'replacement', p_replacement,
    'reason', v_reason
  )::text, 'UTF8'), 'sha256'), 'hex');

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    p_household_id::text || ':' || v_actor::text || ':correction:' || v_key,
    0
  ));

  select * into v_existing
  from private.transaction_correction_requests r
  where r.household_id = p_household_id
    and r.actor_profile_id = v_actor
    and r.idempotency_key = v_key;
  if found then
    if v_existing.request_hash is distinct from v_request_hash then
      raise exception 'idempotency key was already used with a different request'
        using errcode = '23505';
    end if;
    return v_existing.response;
  end if;

  select * into v_original
  from public.transactions t
  where t.household_id = p_household_id
    and t.id = p_transaction_id;
  if not found then
    select * into v_original_link
    from public.transfer_links tl
    where tl.household_id = p_household_id
      and tl.id = p_transaction_id;
    if not found then
      raise exception 'transaction not found' using errcode = 'P0002';
    end if;
    select * into strict v_original
    from public.transactions t
    where t.household_id = p_household_id
      and t.id = v_original_link.transfer_out_transaction_id;
  else
    select * into v_original_link
    from public.transfer_links tl
    where tl.household_id = p_household_id
      and (
        tl.transfer_out_transaction_id = v_original.id
        or tl.transfer_in_transaction_id = v_original.id
      );
  end if;
  if v_original_link.id is not null and p_transaction_id <> v_original_link.id then
    raise exception 'use the logical transfer activity id'
      using errcode = '23514';
  end if;
  if v_original_link.id is null
    and v_original.direction not in ('expense', 'income') then
    raise exception 'only expenses, income and logical transfers can be corrected'
      using errcode = '23514';
  end if;
  v_activity_id := coalesce(v_original_link.id, v_original.id);
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:ledger-activity:' || p_household_id::text || ':' || v_activity_id::text,
    0
  ));
  select * into strict v_original
  from public.transactions t
  where t.household_id = p_household_id and t.id = v_original.id;
  if v_original.status <> 'posted' then
    raise exception 'only posted transactions can be corrected'
      using errcode = '23514';
  end if;
  begin
    v_kind := p_replacement ->> 'kind';
    v_amount_paise := (p_replacement ->> 'amount_paise')::bigint;
    v_currency := upper(p_replacement ->> 'currency');
    v_occurred_at := (p_replacement ->> 'occurred_at')::timestamptz;
    v_note := nullif(p_replacement ->> 'note', '');
    if v_kind = 'transfer' then
      v_source_account_id := (p_replacement ->> 'source_account_id')::uuid;
      v_destination_account_id := (p_replacement ->> 'destination_account_id')::uuid;
    else
      v_account_id := (p_replacement ->> 'account_id')::uuid;
      v_category_name := nullif(trim(p_replacement ->> 'category_name'), '');
      v_paid_by_member_id := (p_replacement ->> 'paid_by_member_id')::uuid;
      v_splits := p_replacement -> 'splits';
      v_merchant := nullif(trim(p_replacement ->> 'merchant'), '');
      v_metadata := coalesce(p_replacement -> 'metadata', '{}'::jsonb);
    end if;
  exception
    when invalid_text_representation or datetime_field_overflow then
      raise exception 'replacement contains an invalid identifier, amount or date'
        using errcode = '22023';
  end;

  if v_kind not in ('expense', 'income', 'transfer')
    or v_amount_paise is null or v_amount_paise <= 0
    or v_currency is null or v_currency !~ '^[A-Z]{3}$'
    or v_occurred_at is null then
    raise exception 'replacement is incomplete or invalid' using errcode = '22023';
  end if;

  if v_original_link.id is not null and v_kind <> 'transfer' then
    raise exception 'a transfer must be corrected as a transfer'
      using errcode = '22023';
  end if;
  if v_original_link.id is null and v_kind = 'transfer' then
    raise exception 'cashflow-to-transfer correction is not supported'
      using errcode = '22023';
  end if;
  if v_kind = 'transfer' then
    if v_source_account_id is null
      or v_destination_account_id is null
      or v_source_account_id = v_destination_account_id then
      raise exception 'transfer replacement requires different source and destination accounts'
        using errcode = '22023';
    end if;
  elsif v_account_id is null
    or v_category_name is null
    or v_paid_by_member_id is null
    or v_splits is null or jsonb_typeof(v_splits) <> 'array'
    or v_merchant is null
    or jsonb_typeof(v_metadata) <> 'object' then
    raise exception 'replacement is incomplete or invalid' using errcode = '22023';
  end if;

  if v_kind <> 'transfer' then
    select array_agg(c.id order by c.id) into v_category_ids
    from public.categories c
    where c.household_id = p_household_id
      and not c.is_archived
      and c.category_type in (v_kind, 'both')
      and lower(pg_catalog.regexp_replace(pg_catalog.btrim(c.name), '\s+', ' ', 'g'))
        = lower(pg_catalog.regexp_replace(v_category_name, '\s+', ' ', 'g'));
    if coalesce(pg_catalog.cardinality(v_category_ids), 0) <> 1 then
      raise exception 'category is not available for this transaction type'
        using errcode = '23514';
    end if;
    v_category_id := v_category_ids[1];
  end if;

  for v_lock_account in
    select distinct affected.account_id
    from (
      select t.account_id
      from public.transactions t
      where t.household_id = p_household_id
        and (
          t.id = v_original.id
          or (
            v_original_link.id is not null
            and t.id in (
              v_original_link.transfer_out_transaction_id,
              v_original_link.transfer_in_transaction_id
            )
          )
        )
      union all
      select case when v_kind = 'transfer' then v_source_account_id else v_account_id end
      union all
      select v_destination_account_id where v_kind = 'transfer'
    ) affected
    where affected.account_id is not null
    order by account_id
  loop
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
      'artha:account-row:' || v_lock_account::text,
      0
    ));
  end loop;

  lock table public.transactions in row exclusive mode;

  perform public.void_transaction(
    p_household_id,
    v_original.id,
    'Correction: ' || v_reason
  );

  v_confirm_key := 'correction-' || encode(extensions.digest(
    convert_to(p_household_id::text || ':' || v_actor::text || ':' || v_key, 'UTF8'),
    'sha256'
  ), 'hex');

  if v_kind = 'transfer' then
    select * into strict v_new_transfer
    from public.create_transfer(
      p_household_id,
      v_source_account_id,
      v_destination_account_id,
      v_amount_paise,
      v_currency,
      v_occurred_at,
      v_confirm_key,
      v_note
    );
    v_replacement_row_id := v_new_transfer.transfer_out_transaction_id;
    v_response := jsonb_build_object(
      'original_transaction_id', p_transaction_id,
      'replacement_transaction_id', v_new_transfer.transfer_link_id,
      'replacement_row_id', v_replacement_row_id,
      'corrected_at', now()
    );
  else
    select * into strict v_replacement
    from public.confirm_transaction(
      p_household_id,
      v_account_id,
      v_category_id,
      v_paid_by_member_id,
      v_kind,
      v_amount_paise,
      v_currency,
      v_occurred_at,
      v_splits,
      v_confirm_key,
      v_merchant,
      v_note,
      v_metadata
    );
    v_replacement_row_id := v_replacement.id;
    v_response := jsonb_build_object(
      'original_transaction_id', p_transaction_id,
      'replacement_transaction_id', v_replacement.id,
      'replacement_row_id', v_replacement.id,
      'corrected_at', now()
    );
  end if;

  insert into private.transaction_correction_requests (
    household_id, actor_profile_id, idempotency_key, request_hash,
    original_transaction_id, replacement_transaction_id, response
  ) values (
    p_household_id, v_actor, v_key, v_request_hash,
    v_original.id, v_replacement_row_id, v_response
  );

  insert into public.audit_events (
    household_id, actor_profile_id, entity_type, entity_id, action, payload
  ) values (
    p_household_id,
    v_actor,
    'transaction',
    p_transaction_id,
    'corrected',
    jsonb_build_object(
      'replacement_transaction_id', v_response ->> 'replacement_transaction_id',
      'reason', v_reason,
      'idempotency_key', v_key
    )
  );

  return v_response;
end;
$$;

revoke all on function public.replace_transaction(uuid, uuid, jsonb, text, text)
  from public, anon, service_role;
grant execute on function public.replace_transaction(uuid, uuid, jsonb, text, text)
  to authenticated;

create table private.transaction_void_requests (
  household_id uuid not null references public.households (id) on delete cascade,
  actor_profile_id uuid not null references public.profiles (id) on delete cascade,
  idempotency_key text not null,
  request_hash text not null check (char_length(request_hash) = 64),
  transaction_id uuid not null,
  response jsonb not null check (jsonb_typeof(response) = 'object'),
  created_at timestamptz not null default now(),
  primary key (household_id, actor_profile_id, idempotency_key),
  constraint transaction_void_transaction_fk
    foreign key (household_id, transaction_id)
    references public.transactions (household_id, id) on delete restrict
);

revoke all on table private.transaction_void_requests
  from public, anon, authenticated, service_role;

create function public.void_ledger_activity(
  p_household_id uuid,
  p_activity_id uuid,
  p_reason text,
  p_idempotency_key text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_actor uuid := auth.uid();
  v_reason text := trim(p_reason);
  v_key text := trim(p_idempotency_key);
  v_request_hash text;
  v_existing private.transaction_void_requests;
  v_transaction_id uuid;
  v_transaction public.transactions;
  v_response jsonb;
  v_link public.transfer_links;
  v_activity_lock_id uuid;
  v_lock_account uuid;
begin
  if v_actor is null or not private.is_household_owner(p_household_id) then
    raise exception 'not authorized for household' using errcode = '42501';
  end if;
  if p_idempotency_key is null or char_length(v_key) not between 8 and 160 then
    raise exception 'idempotency_key is required (8-160 characters)'
      using errcode = '22023';
  end if;
  if p_reason is null or char_length(v_reason) not between 1 and 500 then
    raise exception 'removal reason must contain 1-500 characters'
      using errcode = '22023';
  end if;

  v_request_hash := encode(extensions.digest(convert_to(jsonb_build_object(
    'household_id', p_household_id,
    'activity_id', p_activity_id,
    'reason', v_reason
  )::text, 'UTF8'), 'sha256'), 'hex');

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    p_household_id::text || ':' || v_actor::text || ':activity-void:' || v_key,
    0
  ));
  select * into v_existing
  from private.transaction_void_requests r
  where r.household_id = p_household_id
    and r.actor_profile_id = v_actor
    and r.idempotency_key = v_key;
  if found then
    if v_existing.request_hash is distinct from v_request_hash then
      raise exception 'idempotency key was already used with a different request'
        using errcode = '23505';
    end if;
    return v_existing.response;
  end if;

  select * into v_link
  from public.transfer_links tl
  where tl.household_id = p_household_id and tl.id = p_activity_id;
  if found then
    v_transaction_id := v_link.transfer_out_transaction_id;
    v_activity_lock_id := v_link.id;
  else
    select t.id into v_transaction_id
    from public.transactions t
    where t.household_id = p_household_id
      and t.id = p_activity_id
      and t.direction in ('expense', 'income');
    v_activity_lock_id := v_transaction_id;
  end if;
  if v_transaction_id is null then
    raise exception 'transaction not found' using errcode = 'P0002';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:ledger-activity:' || p_household_id::text || ':' || v_activity_lock_id::text,
    0
  ));

  for v_lock_account in
    select distinct t.account_id
    from public.transactions t
    where t.household_id = p_household_id
      and (
        t.id = v_transaction_id
        or (
          v_link.id is not null
          and t.id in (
            v_link.transfer_out_transaction_id,
            v_link.transfer_in_transaction_id
          )
        )
      )
    order by t.account_id
  loop
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
      'artha:account-row:' || v_lock_account::text,
      0
    ));
  end loop;

  lock table public.transactions in row exclusive mode;

  select * into strict v_transaction
  from public.transactions t
  where t.household_id = p_household_id and t.id = v_transaction_id;
  if v_transaction.status <> 'posted' then
    raise exception 'only posted transactions can be removed'
      using errcode = '23514';
  end if;

  select * into strict v_transaction
  from public.void_transaction(p_household_id, v_transaction_id, v_reason);
  v_response := jsonb_build_object(
    'id', p_activity_id,
    'transaction_id', v_transaction_id,
    'deleted', true,
    'status', v_transaction.status,
    'voided_at', v_transaction.voided_at
  );

  insert into private.transaction_void_requests (
    household_id, actor_profile_id, idempotency_key,
    request_hash, transaction_id, response
  ) values (
    p_household_id, v_actor, v_key,
    v_request_hash, v_transaction_id, v_response
  );
  return v_response;
end;
$$;

revoke all on function public.void_ledger_activity(uuid, uuid, text, text)
  from public, anon, service_role;
grant execute on function public.void_ledger_activity(uuid, uuid, text, text)
  to authenticated;

-- All user-facing removal now goes through the owner-only, idempotent logical
-- activity command above. Keep the lower-level audited primitive private to
-- database-owned functions.
revoke all on function public.void_transaction(uuid, uuid, text)
  from public, anon, authenticated, service_role;

create function public.list_ledger_activity_page(
  p_household_id uuid,
  p_limit integer default 100,
  p_before_occurred_at timestamptz default null,
  p_before_created_at timestamptz default null,
  p_before_id uuid default null
)
returns table (
  id uuid,
  kind text,
  amount_paise bigint,
  personal_share_paise bigint,
  description text,
  category text,
  paid_by_member_id uuid,
  source_account_id uuid,
  destination_account_id uuid,
  settlement_member_id uuid,
  settlement_direction text,
  occurred_at timestamptz,
  notes text,
  splits jsonb,
  is_deleted boolean,
  created_at timestamptz,
  updated_at timestamptz,
  account_delta_paise bigint,
  member_balance_deltas jsonb
)
language plpgsql
stable
security definer
set search_path = ''
set row_security = off
as $$
begin
  if auth.uid() is null or not private.is_household_owner(p_household_id) then
    raise exception 'not authorized for household' using errcode = '42501';
  end if;
  if p_limit is null or p_limit not between 1 and 201 then
    raise exception 'limit must be between 1 and 201' using errcode = '22023';
  end if;
  if (p_before_occurred_at is null) <> (p_before_created_at is null)
    or (p_before_occurred_at is null) <> (p_before_id is null) then
    raise exception 'ledger cursor must be complete' using errcode = '22023';
  end if;

  return query
  with owner_member as materialized (
    select hm.id
    from public.household_members hm
    where hm.household_id = p_household_id
      and hm.profile_id = auth.uid()
      and hm.role = 'owner'
      and hm.is_active
    limit 1
  ),
  ordinary_activity as (
    select
      t.id,
      t.direction as kind,
      t.amount_paise,
      coalesce(owner_split.amount_paise, 0::bigint) as personal_share_paise,
      coalesce(t.merchant, case when t.direction = 'income' then 'Income' else 'Expense' end)
        as description,
      c.name as category,
      t.paid_by_member_id,
      t.account_id as source_account_id,
      null::uuid as destination_account_id,
      null::uuid as settlement_member_id,
      null::text as settlement_direction,
      t.occurred_at,
      t.note as notes,
      coalesce(shared.splits, '[]'::jsonb) as splits,
      false as is_deleted,
      t.created_at,
      t.created_at as updated_at,
      t.amount_paise * case when t.direction = 'income' then 1 else -1 end
        as account_delta_paise,
      coalesce(shared.splits, '[]'::jsonb) as member_balance_deltas
    from public.transactions t
    cross join owner_member owner
    left join public.categories c
      on c.household_id = t.household_id and c.id = t.category_id
    left join lateral (
      select ts.amount_paise
      from public.transaction_splits ts
      where ts.household_id = t.household_id
        and ts.transaction_id = t.id
        and ts.member_id = owner.id
      limit 1
    ) owner_split on true
    left join lateral (
      select jsonb_agg(
        jsonb_build_object('member_id', ts.member_id, 'amount_paise', ts.amount_paise)
        order by ts.member_id
      ) as splits
      from public.transaction_splits ts
      where ts.household_id = t.household_id
        and ts.transaction_id = t.id
        and ts.member_id <> owner.id
    ) shared on true
    where t.household_id = p_household_id
      and t.status = 'posted'
      and t.direction in ('expense', 'income')
  ),
  transfer_activity as (
    select
      tl.id,
      'transfer'::text as kind,
      transfer_out.amount_paise,
      transfer_out.amount_paise as personal_share_paise,
      coalesce(transfer_out.note, 'Account transfer') as description,
      'Transfer'::text as category,
      null::uuid as paid_by_member_id,
      transfer_out.account_id as source_account_id,
      transfer_in.account_id as destination_account_id,
      null::uuid as settlement_member_id,
      null::text as settlement_direction,
      transfer_out.occurred_at,
      transfer_out.note as notes,
      '[]'::jsonb as splits,
      false as is_deleted,
      tl.created_at,
      tl.created_at as updated_at,
      0::bigint as account_delta_paise,
      '[]'::jsonb as member_balance_deltas
    from public.transfer_links tl
    join public.transactions transfer_out
      on transfer_out.household_id = tl.household_id
      and transfer_out.id = tl.transfer_out_transaction_id
      and transfer_out.direction = 'transfer_out'
      and transfer_out.status = 'posted'
    join public.transactions transfer_in
      on transfer_in.household_id = tl.household_id
      and transfer_in.id = tl.transfer_in_transaction_id
      and transfer_in.direction = 'transfer_in'
      and transfer_in.status = 'posted'
    where tl.household_id = p_household_id
  ),
  settlement_activity as (
    select
      movement.id,
      'settlement'::text as kind,
      s.amount_paise,
      0::bigint as personal_share_paise,
      case
        when s.payer_member_id = owner.id then 'Repayment to ' || other_member.display_name
        else 'Repayment from ' || other_member.display_name
      end as description,
      'Shared repayment'::text as category,
      s.payer_member_id as paid_by_member_id,
      s.account_id as source_account_id,
      null::uuid as destination_account_id,
      other_member.id as settlement_member_id,
      s.account_direction as settlement_direction,
      s.settled_at as occurred_at,
      s.note as notes,
      '[]'::jsonb as splits,
      false as is_deleted,
      movement.created_at,
      movement.created_at as updated_at,
      s.amount_paise * case when s.account_direction = 'settlement_in' then 1 else -1 end
        as account_delta_paise,
      jsonb_build_array(jsonb_build_object(
        'member_id', other_member.id,
        'amount_paise', s.amount_paise * case when s.payer_member_id = owner.id then 1 else -1 end
      )) as member_balance_deltas
    from public.settlements s
    join owner_member owner on owner.id in (s.payer_member_id, s.payee_member_id)
    join public.household_members other_member
      on other_member.household_id = s.household_id
      and other_member.id = case
        when s.payer_member_id = owner.id then s.payee_member_id
        else s.payer_member_id
      end
    join public.transactions movement
      on movement.household_id = s.household_id
      and movement.id = s.transaction_id
      and movement.status = 'posted'
    where s.household_id = p_household_id
  ),
  adjustment_activity as (
    select
      t.id,
      'adjustment'::text as kind,
      t.amount_paise,
      0::bigint as personal_share_paise,
      'Balance correction'::text as description,
      'Balance correction'::text as category,
      null::uuid as paid_by_member_id,
      t.account_id as source_account_id,
      null::uuid as destination_account_id,
      null::uuid as settlement_member_id,
      t.direction as settlement_direction,
      t.occurred_at,
      t.note as notes,
      '[]'::jsonb as splits,
      false as is_deleted,
      t.created_at,
      t.created_at as updated_at,
      t.amount_paise * case when t.direction = 'adjustment_in' then 1 else -1 end
        as account_delta_paise,
      '[]'::jsonb as member_balance_deltas
    from public.transactions t
    where t.household_id = p_household_id
      and t.status = 'posted'
      and t.direction in ('adjustment_in', 'adjustment_out')
  ),
  logical_activity as (
    select * from ordinary_activity
    union all
    select * from transfer_activity
    union all
    select * from settlement_activity
    union all
    select * from adjustment_activity
  )
  select activity.*
  from logical_activity activity
  where p_before_occurred_at is null
    or (activity.occurred_at, activity.created_at, activity.id)
      < (p_before_occurred_at, p_before_created_at, p_before_id)
  order by activity.occurred_at desc, activity.created_at desc, activity.id desc
  limit p_limit;
end;
$$;

revoke all on function public.list_ledger_activity_page(
  uuid, integer, timestamptz, timestamptz, uuid
) from public, anon, service_role;
grant execute on function public.list_ledger_activity_page(
  uuid, integer, timestamptz, timestamptz, uuid
) to authenticated;

create function public.search_ledger_activity(
  p_household_id uuid,
  p_query text,
  p_limit integer default 200
)
returns table (
  id uuid,
  kind text,
  amount_paise bigint,
  personal_share_paise bigint,
  description text,
  category text,
  paid_by_member_id uuid,
  source_account_id uuid,
  destination_account_id uuid,
  settlement_member_id uuid,
  settlement_direction text,
  occurred_at timestamptz,
  notes text,
  splits jsonb,
  is_deleted boolean,
  created_at timestamptz,
  updated_at timestamptz,
  account_delta_paise bigint,
  member_balance_deltas jsonb
)
language plpgsql
stable
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_query text := lower(trim(p_query));
begin
  if auth.uid() is null or not private.is_household_owner(p_household_id) then
    raise exception 'not authorized for household' using errcode = '42501';
  end if;
  if p_query is null or char_length(v_query) not between 1 and 120 then
    raise exception 'query must contain 1-120 characters' using errcode = '22023';
  end if;
  if p_limit is null or p_limit not between 1 and 200 then
    raise exception 'limit must be between 1 and 200' using errcode = '22023';
  end if;

  return query
  with owner_member as materialized (
    select hm.id
    from public.household_members hm
    where hm.household_id = p_household_id
      and hm.profile_id = auth.uid()
      and hm.role = 'owner'
      and hm.is_active
    limit 1
  ),
  ordinary_activity as (
    select
      t.id,
      t.direction as kind,
      t.amount_paise,
      coalesce(owner_split.amount_paise, 0::bigint) as personal_share_paise,
      coalesce(t.merchant, case when t.direction = 'income' then 'Income' else 'Expense' end)
        as description,
      c.name as category,
      t.paid_by_member_id,
      t.account_id as source_account_id,
      null::uuid as destination_account_id,
      null::uuid as settlement_member_id,
      null::text as settlement_direction,
      t.occurred_at,
      t.note as notes,
      coalesce(shared.splits, '[]'::jsonb) as splits,
      false as is_deleted,
      t.created_at,
      t.created_at as updated_at,
      t.amount_paise * case when t.direction = 'income' then 1 else -1 end
        as account_delta_paise,
      coalesce(shared.splits, '[]'::jsonb) as member_balance_deltas,
      source_account.name as source_account_name,
      null::text as destination_account_name
    from public.transactions t
    cross join owner_member owner
    join public.accounts source_account
      on source_account.household_id = t.household_id
      and source_account.id = t.account_id
    left join public.categories c
      on c.household_id = t.household_id and c.id = t.category_id
    left join lateral (
      select ts.amount_paise
      from public.transaction_splits ts
      where ts.household_id = t.household_id
        and ts.transaction_id = t.id
        and ts.member_id = owner.id
      limit 1
    ) owner_split on true
    left join lateral (
      select jsonb_agg(
        jsonb_build_object('member_id', ts.member_id, 'amount_paise', ts.amount_paise)
        order by ts.member_id
      ) as splits
      from public.transaction_splits ts
      where ts.household_id = t.household_id
        and ts.transaction_id = t.id
        and ts.member_id <> owner.id
    ) shared on true
    where t.household_id = p_household_id
      and t.status = 'posted'
      and t.direction in ('expense', 'income')
  ),
  transfer_activity as (
    select
      tl.id,
      'transfer'::text as kind,
      transfer_out.amount_paise,
      transfer_out.amount_paise as personal_share_paise,
      coalesce(transfer_out.note, 'Account transfer') as description,
      'Transfer'::text as category,
      null::uuid as paid_by_member_id,
      transfer_out.account_id as source_account_id,
      transfer_in.account_id as destination_account_id,
      null::uuid as settlement_member_id,
      null::text as settlement_direction,
      transfer_out.occurred_at,
      transfer_out.note as notes,
      '[]'::jsonb as splits,
      false as is_deleted,
      tl.created_at,
      tl.created_at as updated_at,
      0::bigint as account_delta_paise,
      '[]'::jsonb as member_balance_deltas,
      source_account.name as source_account_name,
      destination_account.name as destination_account_name
    from public.transfer_links tl
    join public.transactions transfer_out
      on transfer_out.household_id = tl.household_id
      and transfer_out.id = tl.transfer_out_transaction_id
      and transfer_out.direction = 'transfer_out'
      and transfer_out.status = 'posted'
    join public.transactions transfer_in
      on transfer_in.household_id = tl.household_id
      and transfer_in.id = tl.transfer_in_transaction_id
      and transfer_in.direction = 'transfer_in'
      and transfer_in.status = 'posted'
    join public.accounts source_account
      on source_account.household_id = tl.household_id
      and source_account.id = transfer_out.account_id
    join public.accounts destination_account
      on destination_account.household_id = tl.household_id
      and destination_account.id = transfer_in.account_id
    where tl.household_id = p_household_id
  ),
  settlement_activity as (
    select
      movement.id,
      'settlement'::text as kind,
      s.amount_paise,
      0::bigint as personal_share_paise,
      case
        when s.payer_member_id = owner.id then 'Repayment to ' || other_member.display_name
        else 'Repayment from ' || other_member.display_name
      end as description,
      'Shared repayment'::text as category,
      s.payer_member_id as paid_by_member_id,
      s.account_id as source_account_id,
      null::uuid as destination_account_id,
      other_member.id as settlement_member_id,
      s.account_direction as settlement_direction,
      s.settled_at as occurred_at,
      s.note as notes,
      '[]'::jsonb as splits,
      false as is_deleted,
      movement.created_at,
      movement.created_at as updated_at,
      s.amount_paise * case when s.account_direction = 'settlement_in' then 1 else -1 end
        as account_delta_paise,
      jsonb_build_array(jsonb_build_object(
        'member_id', other_member.id,
        'amount_paise', s.amount_paise * case when s.payer_member_id = owner.id then 1 else -1 end
      )) as member_balance_deltas,
      source_account.name as source_account_name,
      other_member.display_name as destination_account_name
    from public.settlements s
    join owner_member owner on owner.id in (s.payer_member_id, s.payee_member_id)
    join public.household_members other_member
      on other_member.household_id = s.household_id
      and other_member.id = case
        when s.payer_member_id = owner.id then s.payee_member_id
        else s.payer_member_id
      end
    join public.transactions movement
      on movement.household_id = s.household_id
      and movement.id = s.transaction_id
      and movement.status = 'posted'
    join public.accounts source_account
      on source_account.household_id = s.household_id
      and source_account.id = s.account_id
    where s.household_id = p_household_id
  ),
  adjustment_activity as (
    select
      t.id,
      'adjustment'::text as kind,
      t.amount_paise,
      0::bigint as personal_share_paise,
      'Balance correction'::text as description,
      'Balance correction'::text as category,
      null::uuid as paid_by_member_id,
      t.account_id as source_account_id,
      null::uuid as destination_account_id,
      null::uuid as settlement_member_id,
      t.direction as settlement_direction,
      t.occurred_at,
      t.note as notes,
      '[]'::jsonb as splits,
      false as is_deleted,
      t.created_at,
      t.created_at as updated_at,
      t.amount_paise * case when t.direction = 'adjustment_in' then 1 else -1 end
        as account_delta_paise,
      '[]'::jsonb as member_balance_deltas,
      source_account.name as source_account_name,
      null::text as destination_account_name
    from public.transactions t
    join public.accounts source_account
      on source_account.household_id = t.household_id
      and source_account.id = t.account_id
    where t.household_id = p_household_id
      and t.status = 'posted'
      and t.direction in ('adjustment_in', 'adjustment_out')
  ),
  logical_activity as (
    select * from ordinary_activity
    union all
    select * from transfer_activity
    union all
    select * from settlement_activity
    union all
    select * from adjustment_activity
  )
  select
    activity.id,
    activity.kind,
    activity.amount_paise,
    activity.personal_share_paise,
    activity.description,
    activity.category,
    activity.paid_by_member_id,
    activity.source_account_id,
    activity.destination_account_id,
    activity.settlement_member_id,
    activity.settlement_direction,
    activity.occurred_at,
    activity.notes,
    activity.splits,
    activity.is_deleted,
    activity.created_at,
    activity.updated_at,
    activity.account_delta_paise,
    activity.member_balance_deltas
  from logical_activity activity
  where position(v_query in lower(concat_ws(
    ' ',
    activity.description,
    activity.category,
    activity.notes,
    activity.source_account_name,
    activity.destination_account_name
  ))) > 0
  order by activity.occurred_at desc, activity.created_at desc, activity.id desc
  limit p_limit;
end;
$$;

revoke all on function public.search_ledger_activity(uuid, text, integer)
  from public, anon, service_role;
grant execute on function public.search_ledger_activity(uuid, text, integer)
  to authenticated;

notify pgrst, 'reload schema';
