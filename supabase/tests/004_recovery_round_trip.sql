-- Full export -> restore acceptance with fictional data. Everything rolls back.
begin;

insert into auth.users (
  id, aud, role, email, encrypted_password, email_confirmed_at,
  raw_app_meta_data, raw_user_meta_data, created_at, updated_at
) values
  (
    '31000000-0000-4000-8000-000000000001', 'authenticated', 'authenticated',
    'recovery-source@example.test', '', now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Recovery Source"}'::jsonb, now(), now()
  ),
  (
    '32000000-0000-4000-8000-000000000002', 'authenticated', 'authenticated',
    'recovery-target@example.test', '', now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Recovery Target"}'::jsonb, now(), now()
  );

insert into public.households (id, name, created_by) values (
  '31000000-1000-4000-8000-000000000001', 'Recovery Source Household',
  '31000000-0000-4000-8000-000000000001'
);

insert into public.household_members (
  id, household_id, display_name, member_type, role
) values (
  '31000000-1100-4000-8000-000000000002',
  '31000000-1000-4000-8000-000000000001',
  'Recovery Participant', 'participant', 'member'
);

insert into public.accounts (
  id, household_id, name, account_type, opening_balance_paise
) values
  (
    '31000000-1200-4000-8000-000000000001',
    '31000000-1000-4000-8000-000000000001',
    'Recovery Bank', 'bank', 100000
  ),
  (
    '31000000-1200-4000-8000-000000000002',
    '31000000-1000-4000-8000-000000000001',
    'Recovery Wallet', 'wallet', 50000
  );

insert into public.categories (id, household_id, name, category_type) values (
  '31000000-1300-4000-8000-000000000001',
  '31000000-1000-4000-8000-000000000001',
  'Recovery Groceries', 'expense'
);

do $$
declare
  v_owner_id uuid;
begin
  select id into strict v_owner_id
  from public.household_members
  where household_id = '31000000-1000-4000-8000-000000000001'
    and role = 'owner';

  insert into public.transactions (
    id, household_id, account_id, category_id, paid_by_member_id, direction,
    amount_paise, currency, occurred_at, merchant, status, idempotency_key,
    request_hash, metadata, created_by
  ) values
    (
      '31000000-1400-4000-8000-000000000001',
      '31000000-1000-4000-8000-000000000001',
      '31000000-1200-4000-8000-000000000001',
      '31000000-1300-4000-8000-000000000001', v_owner_id,
      'expense', 12000, 'INR', '2026-08-01T12:00:00Z',
      'Recovery Market', 'posted', 'recovery-expense-1', repeat('a', 64),
      '{"source":"round-trip-test"}'::jsonb,
      '31000000-0000-4000-8000-000000000001'
    ),
    (
      '31000000-1400-4000-8000-000000000002',
      '31000000-1000-4000-8000-000000000001',
      '31000000-1200-4000-8000-000000000001', null, null,
      'transfer_out', 20000, 'INR', '2026-08-02T12:00:00Z',
      null, 'posted', null, null, '{}'::jsonb,
      '31000000-0000-4000-8000-000000000001'
    ),
    (
      '31000000-1400-4000-8000-000000000003',
      '31000000-1000-4000-8000-000000000001',
      '31000000-1200-4000-8000-000000000002', null, null,
      'transfer_in', 20000, 'INR', '2026-08-02T12:00:00Z',
      null, 'posted', null, null, '{}'::jsonb,
      '31000000-0000-4000-8000-000000000001'
    );

  insert into public.transaction_splits (
    household_id, transaction_id, member_id, amount_paise
  ) values (
    '31000000-1000-4000-8000-000000000001',
    '31000000-1400-4000-8000-000000000001', v_owner_id, 12000
  );
end;
$$;

insert into public.transfer_links (
  id, household_id, transfer_out_transaction_id, transfer_in_transaction_id,
  created_by, idempotency_key, request_hash
) values (
  '31000000-1500-4000-8000-000000000001',
  '31000000-1000-4000-8000-000000000001',
  '31000000-1400-4000-8000-000000000002',
  '31000000-1400-4000-8000-000000000003',
  '31000000-0000-4000-8000-000000000001',
  'recovery-transfer-1', repeat('b', 64)
);

insert into public.merchant_rules (
  household_id, merchant_pattern, category_id, account_id, created_by
) values (
  '31000000-1000-4000-8000-000000000001', 'Recovery Market',
  '31000000-1300-4000-8000-000000000001',
  '31000000-1200-4000-8000-000000000001',
  '31000000-0000-4000-8000-000000000001'
);

set local role authenticated;
select set_config(
  'request.jwt.claim.sub', '31000000-0000-4000-8000-000000000001', true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

create temp table recovery_round_trip_bundle on commit drop as
select public.export_household_bundle() as bundle;

select set_config(
  'request.jwt.claim.sub', '32000000-0000-4000-8000-000000000002', true
);

create temp table recovery_round_trip_result on commit drop as
select public.restore_household_bundle(
  (select bundle from recovery_round_trip_bundle), 'recovery-round-trip-1'
) as result;

do $$
declare
  v_restored_household uuid;
  v_replay jsonb;
  v_rows integer;
  v_balances bigint[];
begin
  select (result ->> 'household_id')::uuid into strict v_restored_household
  from recovery_round_trip_result;

  if v_restored_household = '31000000-1000-4000-8000-000000000001' then
    raise exception 'restore reused the source household id';
  end if;
  if public.get_current_household() <> v_restored_household then
    raise exception 'restored household is not owned by the target user';
  end if;

  select count(*) into v_rows from public.accounts
  where household_id = v_restored_household;
  if v_rows <> 2 then raise exception 'expected 2 restored accounts, got %', v_rows; end if;
  select count(*) into v_rows from public.transactions
  where household_id = v_restored_household;
  if v_rows <> 3 then raise exception 'expected 3 restored transactions, got %', v_rows; end if;
  select count(*) into v_rows from public.transfer_links
  where household_id = v_restored_household;
  if v_rows <> 1 then raise exception 'expected 1 restored transfer, got %', v_rows; end if;
  select count(*) into v_rows from public.merchant_rules
  where household_id = v_restored_household;
  if v_rows <> 1 then raise exception 'expected 1 restored merchant rule, got %', v_rows; end if;

  select array_agg(balance_paise order by balance_paise)
  into v_balances
  from public.get_account_balances(v_restored_household);
  if v_balances <> array[68000::bigint, 70000::bigint] then
    raise exception 'restored balances are incorrect: %', v_balances;
  end if;

  select public.restore_household_bundle(
    (select bundle from recovery_round_trip_bundle), 'recovery-round-trip-1'
  ) into v_replay;
  if coalesce((v_replay ->> 'idempotent_replay')::boolean, false) is not true
     or (v_replay ->> 'household_id')::uuid <> v_restored_household then
    raise exception 'restore idempotency replay failed';
  end if;
end;
$$;

reset role;
rollback;
