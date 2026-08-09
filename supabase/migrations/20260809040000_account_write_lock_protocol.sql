-- Serialize every account-affecting ledger command with account archival.
-- The existing validated/idempotent implementations remain private; public
-- wrappers acquire one shared per-account lock before those implementations run.

alter function public.confirm_transaction(
  uuid, uuid, uuid, uuid, text, bigint, text, timestamptz,
  jsonb, text, text, text, jsonb
) set schema private;
alter function private.confirm_transaction(
  uuid, uuid, uuid, uuid, text, bigint, text, timestamptz,
  jsonb, text, text, text, jsonb
) rename to confirm_transaction_unlocked;

alter function public.create_transfer(
  uuid, uuid, uuid, bigint, text, timestamptz, text, text
) set schema private;
alter function private.create_transfer(
  uuid, uuid, uuid, bigint, text, timestamptz, text, text
) rename to create_transfer_unlocked;

alter function public.create_settlement(
  uuid, uuid, uuid, uuid, text, bigint, text, timestamptz, text, text
) set schema private;
alter function private.create_settlement(
  uuid, uuid, uuid, uuid, text, bigint, text, timestamptz, text, text
) rename to create_settlement_unlocked;

alter function public.void_transaction(uuid, uuid, text) set schema private;
alter function private.void_transaction(uuid, uuid, text)
  rename to void_transaction_unlocked;

revoke all on function private.confirm_transaction_unlocked(
  uuid, uuid, uuid, uuid, text, bigint, text, timestamptz,
  jsonb, text, text, text, jsonb
) from public, anon, authenticated, service_role;
revoke all on function private.create_transfer_unlocked(
  uuid, uuid, uuid, bigint, text, timestamptz, text, text
) from public, anon, authenticated, service_role;
revoke all on function private.create_settlement_unlocked(
  uuid, uuid, uuid, uuid, text, bigint, text, timestamptz, text, text
) from public, anon, authenticated, service_role;
revoke all on function private.void_transaction_unlocked(uuid, uuid, text)
  from public, anon, authenticated, service_role;

create function public.confirm_transaction(
  p_household_id uuid,
  p_account_id uuid,
  p_category_id uuid,
  p_paid_by_member_id uuid,
  p_direction text,
  p_amount_paise bigint,
  p_currency text,
  p_occurred_at timestamptz,
  p_splits jsonb,
  p_idempotency_key text,
  p_merchant text default null,
  p_note text default null,
  p_metadata jsonb default '{}'::jsonb
)
returns public.transactions
language plpgsql
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_transaction public.transactions;
  v_canonical_splits jsonb;
  v_request_hash text;
begin
  if auth.uid() is null or not private.is_household_member(p_household_id) then
    raise exception 'not authorized for household' using errcode = '42501';
  end if;
  if p_idempotency_key is null
    or char_length(trim(p_idempotency_key)) not between 8 and 160 then
    raise exception 'idempotency_key is required (8-160 characters)'
      using errcode = '22023';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    p_household_id::text || ':' || auth.uid()::text || ':confirm:' || trim(p_idempotency_key),
    0
  ));
  select * into v_transaction
  from public.transactions t
  where t.household_id = p_household_id
    and t.created_by = auth.uid()
    and t.idempotency_key = trim(p_idempotency_key);
  if found then
    select jsonb_agg(
      jsonb_build_object(
        'member_id', (s.value ->> 'member_id')::uuid,
        'amount_paise', (s.value ->> 'amount_paise')::bigint
      ) order by (s.value ->> 'member_id')::uuid
    ) into v_canonical_splits
    from jsonb_array_elements(p_splits) s(value);
    v_request_hash := encode(extensions.digest(convert_to(jsonb_build_object(
      'household_id', p_household_id,
      'account_id', p_account_id,
      'category_id', p_category_id,
      'paid_by_member_id', p_paid_by_member_id,
      'direction', p_direction,
      'amount_paise', p_amount_paise,
      'currency', p_currency,
      'occurred_at', p_occurred_at,
      'splits', v_canonical_splits,
      'merchant', nullif(trim(p_merchant), ''),
      'note', p_note,
      'metadata', p_metadata
    )::text, 'UTF8'), 'sha256'), 'hex');
    if v_transaction.request_hash is distinct from v_request_hash then
      raise exception 'idempotency key was already used with a different request'
        using errcode = '23505';
    end if;
    return v_transaction;
  end if;

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:account-row:' || p_account_id::text,
    0
  ));

  select * into strict v_transaction
  from private.confirm_transaction_unlocked(
    p_household_id,
    p_account_id,
    p_category_id,
    p_paid_by_member_id,
    p_direction,
    p_amount_paise,
    p_currency,
    p_occurred_at,
    p_splits,
    p_idempotency_key,
    p_merchant,
    p_note,
    p_metadata
  );
  return v_transaction;
end;
$$;

create function public.create_transfer(
  p_household_id uuid,
  p_from_account_id uuid,
  p_to_account_id uuid,
  p_amount_paise bigint,
  p_currency text,
  p_occurred_at timestamptz,
  p_idempotency_key text,
  p_note text default null
)
returns table (
  transfer_link_id uuid,
  transfer_out_transaction_id uuid,
  transfer_in_transaction_id uuid
)
language plpgsql
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_link public.transfer_links;
  v_request_hash text;
begin
  if auth.uid() is null or not private.is_household_member(p_household_id) then
    raise exception 'not authorized for household' using errcode = '42501';
  end if;
  if p_idempotency_key is null
    or char_length(trim(p_idempotency_key)) not between 8 and 160 then
    raise exception 'idempotency_key is required (8-160 characters)'
      using errcode = '22023';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    p_household_id::text || ':' || auth.uid()::text || ':transfer:' || trim(p_idempotency_key),
    0
  ));
  select * into v_link
  from public.transfer_links tl
  where tl.household_id = p_household_id
    and tl.created_by = auth.uid()
    and tl.idempotency_key = trim(p_idempotency_key);
  if found then
    v_request_hash := encode(extensions.digest(convert_to(jsonb_build_object(
      'household_id', p_household_id,
      'from_account_id', p_from_account_id,
      'to_account_id', p_to_account_id,
      'amount_paise', p_amount_paise,
      'currency', p_currency,
      'occurred_at', p_occurred_at,
      'note', p_note
    )::text, 'UTF8'), 'sha256'), 'hex');
    if v_link.request_hash is distinct from v_request_hash then
      raise exception 'idempotency key was already used with a different request'
        using errcode = '23505';
    end if;
    return query select
      v_link.id,
      v_link.transfer_out_transaction_id,
      v_link.transfer_in_transaction_id;
    return;
  end if;

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:account-row:' || least(p_from_account_id, p_to_account_id)::text,
    0
  ));
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:account-row:' || greatest(p_from_account_id, p_to_account_id)::text,
    0
  ));

  return query
  select *
  from private.create_transfer_unlocked(
    p_household_id,
    p_from_account_id,
    p_to_account_id,
    p_amount_paise,
    p_currency,
    p_occurred_at,
    p_idempotency_key,
    p_note
  );
end;
$$;

create function public.create_settlement(
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
begin
  if auth.uid() is null or not private.is_household_member(p_household_id) then
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

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'artha:account-row:' || p_account_id::text,
    0
  ));

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

create function public.void_transaction(
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
  v_account_id uuid;
  v_transaction public.transactions;
begin
  if auth.uid() is null or not private.is_household_member(p_household_id) then
    raise exception 'not authorized for household' using errcode = '42501';
  end if;

  for v_account_id in
    select distinct t.account_id
    from public.transactions t
    where t.household_id = p_household_id
      and (
        t.id = p_transaction_id
        or t.id in (
          select tl.transfer_out_transaction_id
          from public.transfer_links tl
          where tl.household_id = p_household_id
            and (
              tl.transfer_out_transaction_id = p_transaction_id
              or tl.transfer_in_transaction_id = p_transaction_id
            )
          union all
          select tl.transfer_in_transaction_id
          from public.transfer_links tl
          where tl.household_id = p_household_id
            and (
              tl.transfer_out_transaction_id = p_transaction_id
              or tl.transfer_in_transaction_id = p_transaction_id
            )
        )
      )
    order by t.account_id
  loop
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
      'artha:account-row:' || v_account_id::text,
      0
    ));
  end loop;

  select * into v_transaction
  from public.transactions t
  where t.household_id = p_household_id and t.id = p_transaction_id;
  if found and v_transaction.status <> 'voided' and exists (
    select 1
    from public.accounts a
    where a.household_id = p_household_id
      and a.is_archived
      and a.id in (
        select distinct t.account_id
        from public.transactions t
        where t.household_id = p_household_id
          and (
            t.id = p_transaction_id
            or t.id in (
              select tl.transfer_out_transaction_id
              from public.transfer_links tl
              where tl.household_id = p_household_id
                and (
                  tl.transfer_out_transaction_id = p_transaction_id
                  or tl.transfer_in_transaction_id = p_transaction_id
                )
              union all
              select tl.transfer_in_transaction_id
              from public.transfer_links tl
              where tl.household_id = p_household_id
                and (
                  tl.transfer_out_transaction_id = p_transaction_id
                  or tl.transfer_in_transaction_id = p_transaction_id
                )
            )
          )
      )
  ) then
    raise exception 'restore archived accounts before voiding their transactions'
      using errcode = '23514';
  end if;

  select * into strict v_transaction
  from private.void_transaction_unlocked(
    p_household_id,
    p_transaction_id,
    p_reason
  );
  return v_transaction;
end;
$$;

revoke all on function public.confirm_transaction(
  uuid, uuid, uuid, uuid, text, bigint, text, timestamptz,
  jsonb, text, text, text, jsonb
) from public, anon, service_role;
revoke all on function public.create_transfer(
  uuid, uuid, uuid, bigint, text, timestamptz, text, text
) from public, anon, service_role;
revoke all on function public.create_settlement(
  uuid, uuid, uuid, uuid, text, bigint, text, timestamptz, text, text
) from public, anon, service_role;
revoke all on function public.void_transaction(uuid, uuid, text)
  from public, anon, service_role;
grant execute on function public.confirm_transaction(
  uuid, uuid, uuid, uuid, text, bigint, text, timestamptz,
  jsonb, text, text, text, jsonb
) to authenticated;
grant execute on function public.create_transfer(
  uuid, uuid, uuid, bigint, text, timestamptz, text, text
) to authenticated;
grant execute on function public.create_settlement(
  uuid, uuid, uuid, uuid, text, bigint, text, timestamptz, text, text
) to authenticated;
grant execute on function public.void_transaction(uuid, uuid, text)
  to authenticated;

notify pgrst, 'reload schema';
