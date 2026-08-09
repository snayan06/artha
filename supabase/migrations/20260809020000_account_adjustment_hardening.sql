-- Serialize balance reconciliation and bind idempotency keys to exact requests.

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
  if char_length(trim(p_idempotency_key)) not between 8 and 200 then
    raise exception 'invalid idempotency key' using errcode = '22023';
  end if;

  v_hash := encode(extensions.digest(convert_to(jsonb_build_object(
    'account_id', p_account_id,
    'actual_balance_paise', p_actual_balance_paise,
    'reason', trim(p_reason),
    'occurred_at', p_occurred_at
  )::text, 'utf8'), 'sha256'), 'hex');

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended('artha:account-adjust:' || p_account_id::text, 0)
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

revoke all on function public.create_balance_adjustment(
  uuid, uuid, bigint, text, timestamptz, text
) from public, anon, service_role;
grant execute on function public.create_balance_adjustment(
  uuid, uuid, bigint, text, timestamptz, text
) to authenticated;

notify pgrst, 'reload schema';
