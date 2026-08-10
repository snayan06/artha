-- Daily-use transaction correction must be atomic, exact-replay idempotent and
-- fully auditable. All fictional rows are rolled back.
begin;

insert into auth.users (
  id, aud, role, email, encrypted_password, email_confirmed_at,
  raw_app_meta_data, raw_user_meta_data, created_at, updated_at
) values (
  '71000000-0000-4000-8000-000000000001',
  'authenticated', 'authenticated', 'daily-use@example.test', '', now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Daily Use Owner"}'::jsonb, now(), now()
);

insert into auth.users (
  id, aud, role, email, encrypted_password, email_confirmed_at,
  raw_app_meta_data, raw_user_meta_data, created_at, updated_at
) values (
  '71000000-0000-4000-8000-000000000002',
  'authenticated', 'authenticated', 'daily-member@example.test', '', now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Daily Use Signed-in Member"}'::jsonb, now(), now()
);

insert into public.households (id, name, created_by) values (
  '71000000-1000-4000-8000-000000000001',
  'Daily Use Household',
  '71000000-0000-4000-8000-000000000001'
);

insert into public.household_members (
  id, household_id, profile_id, display_name, member_type, role
) values
(
  '71000000-1300-4000-8000-000000000001',
  '71000000-1000-4000-8000-000000000001',
  null, 'Daily Family Member', 'participant', 'member'
),
(
  '71000000-1300-4000-8000-000000000002',
  '71000000-1000-4000-8000-000000000001',
  '71000000-0000-4000-8000-000000000002',
  'Daily Signed-in Member', 'user', 'member'
);

insert into public.accounts (
  id, household_id, name, account_type, opening_balance_paise
) values
  (
    '71000000-1100-4000-8000-000000000001',
    '71000000-1000-4000-8000-000000000001',
    'Daily Bank A', 'bank', 100000
  ),
  (
    '71000000-1100-4000-8000-000000000002',
    '71000000-1000-4000-8000-000000000001',
    'Daily Bank B', 'bank', 50000
  );

insert into public.categories (id, household_id, name, category_type, is_archived) values
  (
    '71000000-1200-4000-8000-000000000001',
    '71000000-1000-4000-8000-000000000001',
    'Daily Food', 'expense', false
  ),
  (
    '71000000-1200-4000-8000-000000000002',
    '71000000-1000-4000-8000-000000000001',
    'Daily Travel', 'expense', false
  ),
  (
    '71000000-1200-4000-8000-000000000003',
    '71000000-1000-4000-8000-000000000001',
    'Daily Travel', 'expense', true
  );

set local role authenticated;
select set_config(
  'request.jwt.claim.sub', '71000000-0000-4000-8000-000000000001', true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

do $$
declare
  v_owner_id uuid;
begin
  select hm.id into strict v_owner_id
  from public.household_members hm
  where hm.household_id = '71000000-1000-4000-8000-000000000001'
    and hm.profile_id = '71000000-0000-4000-8000-000000000001';

  perform * from public.confirm_transaction(
    '71000000-1000-4000-8000-000000000001',
    '71000000-1100-4000-8000-000000000001',
    '71000000-1200-4000-8000-000000000001',
    v_owner_id,
    'expense', 10000, 'INR', '2026-08-10T10:00:00Z'::timestamptz,
    jsonb_build_array(jsonb_build_object(
      'member_id', v_owner_id, 'amount_paise', 10000
    )),
    'daily-original-0001', 'Original purchase', 'Original note', '{}'::jsonb
  );

  perform * from public.create_transfer(
    '71000000-1000-4000-8000-000000000001',
    '71000000-1100-4000-8000-000000000001',
    '71000000-1100-4000-8000-000000000002',
    20000, 'INR', '2026-08-10T11:00:00Z'::timestamptz,
    'daily-transfer-original-0001', 'Original transfer'
  );
end;
$$;

do $$
declare
  v_original_id uuid;
  v_owner_id uuid;
begin
  select t.id into strict v_original_id
  from public.transactions t
  where t.household_id = '71000000-1000-4000-8000-000000000001'
    and t.idempotency_key = 'daily-original-0001';
  select hm.id into strict v_owner_id
  from public.household_members hm
  where hm.household_id = '71000000-1000-4000-8000-000000000001'
    and hm.profile_id = '71000000-0000-4000-8000-000000000001';

  perform set_config(
    'request.jwt.claim.sub', '71000000-0000-4000-8000-000000000002', true
  );
  begin
    perform public.replace_transaction(
      '71000000-1000-4000-8000-000000000001',
      v_original_id,
      jsonb_build_object(
        'kind', 'expense',
        'account_id', '71000000-1100-4000-8000-000000000001',
        'category_name', 'Daily Food',
        'paid_by_member_id', v_owner_id,
        'amount_paise', 10000,
        'currency', 'INR',
        'occurred_at', '2026-08-10T10:00:00Z',
        'splits', jsonb_build_array(jsonb_build_object(
          'member_id', v_owner_id, 'amount_paise', 10000
        )),
        'merchant', 'Unauthorized correction',
        'metadata', '{}'::jsonb
      ),
      'Participant must not correct',
      'daily-member-correction-0001'
    );
    raise exception 'non-owner directly corrected a transaction';
  exception
    when insufficient_privilege then null;
  end;

  begin
    perform public.void_ledger_activity(
      '71000000-1000-4000-8000-000000000001',
      v_original_id,
      'Participant must not remove',
      'daily-member-removal-0001'
    );
    raise exception 'non-owner directly removed a transaction';
  exception
    when insufficient_privilege then null;
  end;

  begin
    perform public.void_transaction(
      '71000000-1000-4000-8000-000000000001',
      v_original_id,
      'Participant must not call the low-level primitive'
    );
    raise exception 'authenticated caller executed the low-level void primitive';
  exception
    when insufficient_privilege then null;
  end;

  perform set_config(
    'request.jwt.claim.sub', '71000000-0000-4000-8000-000000000001', true
  );
end;
$$;

do $$
declare
  v_original_id uuid;
  v_owner_id uuid;
  v_first jsonb;
  v_replay jsonb;
  v_replacement_id uuid;
  v_old_status text;
  v_new_amount bigint;
  v_audit_rows integer;
  v_balance_a bigint;
  v_balance_b bigint;
begin
  select t.id into strict v_original_id
  from public.transactions t
  where t.household_id = '71000000-1000-4000-8000-000000000001'
    and t.idempotency_key = 'daily-original-0001';
  select hm.id into strict v_owner_id
  from public.household_members hm
  where hm.household_id = '71000000-1000-4000-8000-000000000001'
    and hm.profile_id = '71000000-0000-4000-8000-000000000001';

  select public.replace_transaction(
    '71000000-1000-4000-8000-000000000001',
    v_original_id,
    jsonb_build_object(
      'kind', 'expense',
      'account_id', '71000000-1100-4000-8000-000000000002',
      'category_name', 'Daily Travel',
      'paid_by_member_id', v_owner_id,
      'amount_paise', 12000,
      'currency', 'INR',
      'occurred_at', '2026-08-09T12:00:00Z',
      'splits', jsonb_build_array(jsonb_build_object(
        'member_id', v_owner_id, 'amount_paise', 12000
      )),
      'merchant', 'Corrected purchase',
      'note', 'Corrected note',
      'metadata', '{}'::jsonb
    ),
    'Corrected amount and account',
    'daily-correction-0001'
  ) into strict v_first;

  select public.replace_transaction(
    '71000000-1000-4000-8000-000000000001',
    v_original_id,
    jsonb_build_object(
      'kind', 'expense',
      'account_id', '71000000-1100-4000-8000-000000000002',
      'category_name', 'Daily Travel',
      'paid_by_member_id', v_owner_id,
      'amount_paise', 12000,
      'currency', 'INR',
      'occurred_at', '2026-08-09T12:00:00Z',
      'splits', jsonb_build_array(jsonb_build_object(
        'member_id', v_owner_id, 'amount_paise', 12000
      )),
      'merchant', 'Corrected purchase',
      'note', 'Corrected note',
      'metadata', '{}'::jsonb
    ),
    'Corrected amount and account',
    'daily-correction-0001'
  ) into strict v_replay;

  if v_first is distinct from v_replay then
    raise exception 'correction replay did not return the exact stored response';
  end if;

  v_replacement_id := (v_first ->> 'replacement_transaction_id')::uuid;
  select status into strict v_old_status
  from public.transactions where id = v_original_id;
  select amount_paise into strict v_new_amount
  from public.transactions where id = v_replacement_id;
  if v_old_status <> 'voided' or v_new_amount <> 12000 then
    raise exception 'correction did not void original and post replacement';
  end if;

  select count(*) into v_audit_rows
  from public.audit_events
  where household_id = '71000000-1000-4000-8000-000000000001'
    and action = 'corrected'
    and entity_id = v_original_id;
  if v_audit_rows <> 1 then
    raise exception 'correction replay created % correction audit rows', v_audit_rows;
  end if;

  select balance_paise into strict v_balance_a
  from public.get_account_balances('71000000-1000-4000-8000-000000000001')
  where account_id = '71000000-1100-4000-8000-000000000001';
  select balance_paise into strict v_balance_b
  from public.get_account_balances('71000000-1000-4000-8000-000000000001')
  where account_id = '71000000-1100-4000-8000-000000000002';
  if v_balance_a <> 80000 or v_balance_b <> 58000 then
    raise exception 'correction balances are wrong: %, %', v_balance_a, v_balance_b;
  end if;

  begin
    perform public.replace_transaction(
      '71000000-1000-4000-8000-000000000001',
      v_original_id,
      jsonb_set(
        jsonb_build_object(
          'kind', 'expense',
          'account_id', '71000000-1100-4000-8000-000000000002',
          'category_name', 'Daily Travel',
          'paid_by_member_id', v_owner_id,
          'amount_paise', 12000,
          'currency', 'INR',
          'occurred_at', '2026-08-09T12:00:00Z',
          'splits', jsonb_build_array(jsonb_build_object(
            'member_id', v_owner_id, 'amount_paise', 12000
          )),
          'merchant', 'Corrected purchase',
          'note', 'Corrected note',
          'metadata', '{}'::jsonb
        ),
        '{amount_paise}', '13000'::jsonb
      ),
      'Corrected amount and account',
      'daily-correction-0001'
    );
    raise exception 'correction accepted a reused key with a different payload';
  exception
    when unique_violation then null;
  end;
end;
$$;

do $$
declare
  v_original_link_id uuid;
  v_original_out_id uuid;
  v_original_in_id uuid;
  v_first jsonb;
  v_replay jsonb;
  v_replacement_link_id uuid;
  v_replacement_out_id uuid;
  v_replacement_in_id uuid;
  v_balance_a bigint;
  v_balance_b bigint;
  v_audit_rows integer;
begin
  select tl.id, tl.transfer_out_transaction_id, tl.transfer_in_transaction_id
  into strict v_original_link_id, v_original_out_id, v_original_in_id
  from public.transfer_links tl
  where tl.household_id = '71000000-1000-4000-8000-000000000001'
    and tl.idempotency_key = 'daily-transfer-original-0001';

  select public.replace_transaction(
    '71000000-1000-4000-8000-000000000001',
    v_original_link_id,
    jsonb_build_object(
      'kind', 'transfer',
      'source_account_id', '71000000-1100-4000-8000-000000000002',
      'destination_account_id', '71000000-1100-4000-8000-000000000001',
      'amount_paise', 15000,
      'currency', 'INR',
      'occurred_at', '2026-08-09T13:00:00Z',
      'note', 'Corrected transfer direction'
    ),
    'Corrected transfer direction and amount',
    'daily-transfer-correction-0001'
  ) into strict v_first;

  select public.replace_transaction(
    '71000000-1000-4000-8000-000000000001',
    v_original_link_id,
    jsonb_build_object(
      'kind', 'transfer',
      'source_account_id', '71000000-1100-4000-8000-000000000002',
      'destination_account_id', '71000000-1100-4000-8000-000000000001',
      'amount_paise', 15000,
      'currency', 'INR',
      'occurred_at', '2026-08-09T13:00:00Z',
      'note', 'Corrected transfer direction'
    ),
    'Corrected transfer direction and amount',
    'daily-transfer-correction-0001'
  ) into strict v_replay;

  if v_first is distinct from v_replay then
    raise exception 'transfer correction replay changed its response';
  end if;

  if exists (
    select 1 from public.transactions
    where id in (v_original_out_id, v_original_in_id) and status <> 'voided'
  ) then
    raise exception 'transfer correction did not void both original rows';
  end if;

  v_replacement_link_id := (v_first ->> 'replacement_transaction_id')::uuid;
  select tl.transfer_out_transaction_id, tl.transfer_in_transaction_id
  into strict v_replacement_out_id, v_replacement_in_id
  from public.transfer_links tl where tl.id = v_replacement_link_id;
  if exists (
    select 1 from public.transactions
    where id in (v_replacement_out_id, v_replacement_in_id) and status <> 'posted'
  ) then
    raise exception 'transfer correction replacement is not fully posted';
  end if;

  select balance_paise into strict v_balance_a
  from public.get_account_balances('71000000-1000-4000-8000-000000000001')
  where account_id = '71000000-1100-4000-8000-000000000001';
  select balance_paise into strict v_balance_b
  from public.get_account_balances('71000000-1000-4000-8000-000000000001')
  where account_id = '71000000-1100-4000-8000-000000000002';
  if v_balance_a <> 115000 or v_balance_b <> 23000 then
    raise exception 'transfer correction balances are wrong: %, %', v_balance_a, v_balance_b;
  end if;

  select count(*) into v_audit_rows
  from public.audit_events
  where household_id = '71000000-1000-4000-8000-000000000001'
    and action = 'corrected'
    and entity_id = v_original_link_id;
  if v_audit_rows <> 1 then
    raise exception 'transfer correction created % correction audit rows', v_audit_rows;
  end if;
end;
$$;

do $$
declare
  v_link_id uuid;
  v_out_id uuid;
  v_in_id uuid;
  v_first jsonb;
  v_replay jsonb;
begin
  select tl.id, tl.transfer_out_transaction_id, tl.transfer_in_transaction_id
  into strict v_link_id, v_out_id, v_in_id
  from public.transfer_links tl
  join public.transactions transfer_out
    on transfer_out.id = tl.transfer_out_transaction_id
    and transfer_out.status = 'posted'
  where tl.household_id = '71000000-1000-4000-8000-000000000001'
  order by tl.created_at desc
  limit 1;

  select public.void_ledger_activity(
    '71000000-1000-4000-8000-000000000001',
    v_link_id,
    'Duplicate transfer',
    'daily-transfer-void-0001'
  ) into strict v_first;
  select public.void_ledger_activity(
    '71000000-1000-4000-8000-000000000001',
    v_link_id,
    'Duplicate transfer',
    'daily-transfer-void-0001'
  ) into strict v_replay;

  if v_first is distinct from v_replay then
    raise exception 'logical transfer void replay changed its response';
  end if;
  if exists (
    select 1 from public.transactions
    where id in (v_out_id, v_in_id) and status <> 'voided'
  ) then
    raise exception 'logical transfer void did not void both transaction rows';
  end if;

  begin
    perform public.void_ledger_activity(
      '71000000-1000-4000-8000-000000000001',
      v_link_id,
      'Different reason',
      'daily-transfer-void-0001'
    );
    raise exception 'logical void accepted a reused key with a different request';
  exception
    when unique_violation then null;
  end;
end;
$$;

do $$
declare
  v_owner_id uuid;
  v_first jsonb;
  v_replay jsonb;
  v_direction text;
  v_balance bigint;
  v_activity record;
begin
  select hm.id into strict v_owner_id
  from public.household_members hm
  where hm.household_id = '71000000-1000-4000-8000-000000000001'
    and hm.profile_id = '71000000-0000-4000-8000-000000000001';

  perform * from public.confirm_transaction(
    '71000000-1000-4000-8000-000000000001',
    '71000000-1100-4000-8000-000000000001',
    '71000000-1200-4000-8000-000000000001',
    v_owner_id,
    'expense', 5000, 'INR', '2026-08-10T13:30:00Z'::timestamptz,
    jsonb_build_array(jsonb_build_object(
      'member_id', '71000000-1300-4000-8000-000000000001',
      'amount_paise', 5000
    )),
    'daily-shared-expense-0001', 'Shared expense', null, '{}'::jsonb
  );

  begin
    perform public.settle_member_balance(
      '71000000-1000-4000-8000-000000000001',
      '71000000-1300-4000-8000-000000000001',
      '71000000-1100-4000-8000-000000000001',
      6000, '2026-08-10T13:55:00Z'::timestamptz,
      'daily-settlement-over-0001', 'Must exceed current balance'
    );
    raise exception 'database accepted an over-settlement';
  exception
    when check_violation then null;
  end;

  select public.settle_member_balance(
    '71000000-1000-4000-8000-000000000001',
    '71000000-1300-4000-8000-000000000001',
    '71000000-1100-4000-8000-000000000001',
    5000, '2026-08-10T14:00:00Z'::timestamptz,
    'daily-settlement-0001', 'Full repayment'
  ) into strict v_first;
  select public.settle_member_balance(
    '71000000-1000-4000-8000-000000000001',
    '71000000-1300-4000-8000-000000000001',
    '71000000-1100-4000-8000-000000000001',
    5000, '2026-08-10T14:00:00Z'::timestamptz,
    'daily-settlement-0001', 'Full repayment'
  ) into strict v_replay;
  if v_first is distinct from v_replay then
    raise exception 'full settlement retry did not replay the exact response';
  end if;
  select t.direction into strict v_direction
  from public.transactions t
  where t.id = (v_first ->> 'transaction_id')::uuid;
  if v_direction <> 'settlement_in' then
    raise exception 'settlement did not preserve the account movement direction';
  end if;
  if (
    select count(*) from public.settlements s
    where s.household_id = '71000000-1000-4000-8000-000000000001'
      and s.id = (v_first ->> 'id')::uuid
  ) <> 1 then
    raise exception 'settlement retry created duplicate rows';
  end if;

  select coalesce((
    select b.balance_paise
    from public.get_member_balances(
      '71000000-1000-4000-8000-000000000001'
    ) b
    where b.member_id = '71000000-1300-4000-8000-000000000001'
  ), 0) into v_balance;
  if v_balance <> 0 or (v_first ->> 'balance_paise')::bigint <> 0 then
    raise exception 'database member balance projection is wrong: %', v_balance;
  end if;

  select * into strict v_activity
  from public.list_ledger_activity_page(
    '71000000-1000-4000-8000-000000000001', 50, null, null, null
  ) activity
  where activity.id = (v_first ->> 'transaction_id')::uuid;
  if v_activity.kind <> 'settlement'
    or v_activity.settlement_member_id
      <> '71000000-1300-4000-8000-000000000001'::uuid
    or v_activity.settlement_direction <> 'settlement_in'
    or v_activity.amount_paise <> 5000 then
    raise exception 'settlement movement is missing or malformed in ledger activity';
  end if;

  select * into strict v_activity
  from public.search_ledger_activity(
    '71000000-1000-4000-8000-000000000001', 'full repayment', 20
  ) activity
  where activity.id = (v_first ->> 'transaction_id')::uuid;

  begin
    perform public.void_ledger_activity(
      '71000000-1000-4000-8000-000000000001',
      (v_first ->> 'transaction_id')::uuid,
      'Must not void settlement movement',
      'daily-settlement-void-0001'
    );
    raise exception 'logical void accepted a settlement movement';
  exception
    when no_data_found then null;
  end;

  begin
    perform public.replace_transaction(
      '71000000-1000-4000-8000-000000000001',
      (v_first ->> 'transaction_id')::uuid,
      jsonb_build_object(
        'kind', 'expense',
        'account_id', '71000000-1100-4000-8000-000000000001',
        'category_name', 'Daily Food',
        'paid_by_member_id', v_owner_id,
        'amount_paise', 2500,
        'currency', 'INR',
        'occurred_at', '2026-08-10T14:00:00Z',
        'splits', jsonb_build_array(jsonb_build_object(
          'member_id', v_owner_id, 'amount_paise', 2500
        )),
        'merchant', 'Must not replace settlement',
        'metadata', '{}'::jsonb
      ),
      'Must not replace settlement movement',
      'daily-settlement-correction-0001'
    );
    raise exception 'correction accepted a settlement movement';
  exception
    when check_violation then null;
  end;
end;
$$;

do $$
declare
  v_current bigint;
  v_adjustment public.transactions;
  v_activity record;
begin
  select b.balance_paise into strict v_current
  from public.get_account_balances('71000000-1000-4000-8000-000000000001') b
  where b.account_id = '71000000-1100-4000-8000-000000000001';

  select * into strict v_adjustment
  from public.create_balance_adjustment(
    '71000000-1000-4000-8000-000000000001',
    '71000000-1100-4000-8000-000000000001',
    v_current + 1234,
    'Statement reconciliation',
    '2026-08-10T14:10:00Z'::timestamptz,
    'daily-adjustment-0001'
  );

  select * into strict v_activity
  from public.list_ledger_activity_page(
    '71000000-1000-4000-8000-000000000001', 50, null, null, null
  ) activity
  where activity.id = v_adjustment.id;
  if v_activity.kind <> 'adjustment'
    or v_activity.settlement_direction <> 'adjustment_in'
    or v_activity.amount_paise <> 1234 then
    raise exception 'balance adjustment is missing or malformed in ledger activity';
  end if;

  select * into strict v_activity
  from public.search_ledger_activity(
    '71000000-1000-4000-8000-000000000001', 'statement reconciliation', 20
  ) activity
  where activity.id = v_adjustment.id;
end;
$$;

do $$
declare
  v_match record;
begin
  select * into strict v_match
  from public.search_ledger_activity(
    '71000000-1000-4000-8000-000000000001',
    'corrected note',
    20
  );
  if v_match.description <> 'Corrected purchase' then
    raise exception 'database search returned the wrong activity';
  end if;
end;
$$;

do $$
declare
  v_first record;
  v_second record;
begin
  select * into strict v_first
  from public.list_ledger_activity_page(
    '71000000-1000-4000-8000-000000000001', 1, null, null, null
  );
  select * into strict v_second
  from public.list_ledger_activity_page(
    '71000000-1000-4000-8000-000000000001',
    1,
    v_first.occurred_at,
    v_first.created_at,
    v_first.id
  );
  if v_second.id = v_first.id or
    (v_second.occurred_at, v_second.created_at, v_second.id)
      >= (v_first.occurred_at, v_first.created_at, v_first.id) then
    raise exception 'stable ledger cursor did not advance to older activity';
  end if;
end;
$$;

reset role;
rollback;
