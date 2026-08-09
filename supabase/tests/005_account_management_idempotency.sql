-- Account-management mutations must be exact idempotent replay boundaries.
-- Every fictional row is rolled back after the behavioral assertions.
begin;

insert into auth.users (
  id, aud, role, email, encrypted_password, email_confirmed_at,
  raw_app_meta_data, raw_user_meta_data, created_at, updated_at
) values (
  '51000000-0000-4000-8000-000000000001',
  'authenticated', 'authenticated', 'account-idempotency@example.test', '', now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Account Idempotency User"}'::jsonb, now(), now()
);

insert into public.households (id, name, created_by) values (
  '51000000-1000-4000-8000-000000000001',
  'Account Idempotency Household',
  '51000000-0000-4000-8000-000000000001'
);

insert into public.accounts (
  id, household_id, name, account_type, opening_balance_paise
) values (
  '51000000-1100-4000-8000-000000000001',
  '51000000-1000-4000-8000-000000000001',
  'Existing Zero Balance', 'bank', 0
);

insert into public.categories (id, household_id, name, category_type) values (
  '51000000-1200-4000-8000-000000000001',
  '51000000-1000-4000-8000-000000000001',
  'Replay Balance Category', 'both'
);

set local role authenticated;
select set_config(
  'request.jwt.claim.sub', '51000000-0000-4000-8000-000000000001', true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

do $$
declare
  v_member_id uuid;
begin
  select hm.id into strict v_member_id
  from public.household_members hm
  where hm.household_id = '51000000-1000-4000-8000-000000000001'
    and hm.profile_id = '51000000-0000-4000-8000-000000000001';

  perform * from public.confirm_transaction(
    '51000000-1000-4000-8000-000000000001',
    '51000000-1100-4000-8000-000000000001',
    '51000000-1200-4000-8000-000000000001',
    v_member_id,
    'income', 10000, 'INR', '2026-08-09T10:00:00Z'::timestamptz,
    jsonb_build_array(jsonb_build_object(
      'member_id', v_member_id, 'amount_paise', 10000
    )),
    'archived-replay-income-0001', 'Replay salary', null, '{}'::jsonb
  );
  perform * from public.confirm_transaction(
    '51000000-1000-4000-8000-000000000001',
    '51000000-1100-4000-8000-000000000001',
    '51000000-1200-4000-8000-000000000001',
    v_member_id,
    'expense', 10000, 'INR', '2026-08-09T10:01:00Z'::timestamptz,
    jsonb_build_array(jsonb_build_object(
      'member_id', v_member_id, 'amount_paise', 10000
    )),
    'archived-replay-expense-0001', 'Replay purchase', null, '{}'::jsonb
  );
end;
$$;

do $$
declare
  v_first public.accounts;
  v_replay public.accounts;
  v_rows integer;
begin
  select * into strict v_first
  from public.create_managed_account(
    '51000000-1000-4000-8000-000000000001',
    'Idempotent Bank', 'bank', 250000, null, null, null,
    'account-idempotency-key-0001'
  );
  select * into strict v_replay
  from public.create_managed_account(
    '51000000-1000-4000-8000-000000000001',
    'Idempotent Bank', 'bank', 250000, null, null, null,
    'account-idempotency-key-0001'
  );

  if to_jsonb(v_first) is distinct from to_jsonb(v_replay) then
    raise exception 'create replay did not return the exact stored response';
  end if;

  select count(*) into v_rows
  from public.audit_events
  where household_id = '51000000-1000-4000-8000-000000000001'
    and action = 'created'
    and payload ->> 'idempotency_key' = 'account-idempotency-key-0001';
  if v_rows <> 1 then
    raise exception 'create replay appended % audit rows instead of 1', v_rows;
  end if;

  begin
    perform * from public.create_managed_account(
      '51000000-1000-4000-8000-000000000001',
      'Different Bank', 'bank', 250000, null, null, null,
      'account-idempotency-key-0001'
    );
    raise exception 'create accepted a reused key with a different payload';
  exception
    when unique_violation then null;
  end;
end;
$$;

do $$
declare
  v_first public.accounts;
  v_replay public.accounts;
  v_rows integer;
begin
  select * into strict v_first
  from public.update_managed_account(
    '51000000-1000-4000-8000-000000000001',
    '51000000-1100-4000-8000-000000000001',
    'Renamed Zero Balance', null, null, null,
    'account-idempotency-key-0001'
  );
  select * into strict v_replay
  from public.update_managed_account(
    '51000000-1000-4000-8000-000000000001',
    '51000000-1100-4000-8000-000000000001',
    'Renamed Zero Balance', null, null, null,
    'account-idempotency-key-0001'
  );

  if to_jsonb(v_first) is distinct from to_jsonb(v_replay) then
    raise exception 'update replay did not return the exact stored response';
  end if;

  select count(*) into v_rows
  from public.audit_events
  where household_id = '51000000-1000-4000-8000-000000000001'
    and action = 'updated'
    and payload ->> 'idempotency_key' = 'account-idempotency-key-0001';
  if v_rows <> 1 then
    raise exception 'update replay appended % audit rows instead of 1', v_rows;
  end if;

  begin
    perform * from public.update_managed_account(
      '51000000-1000-4000-8000-000000000001',
      '51000000-1100-4000-8000-000000000001',
      'A Different Rename', null, null, null,
      'account-idempotency-key-0001'
    );
    raise exception 'update accepted a reused key with a different payload';
  exception
    when unique_violation then null;
  end;
end;
$$;

do $$
declare
  v_first public.accounts;
  v_replay public.accounts;
  v_rows integer;
begin
  select * into strict v_first
  from public.set_managed_account_archived(
    '51000000-1000-4000-8000-000000000001',
    '51000000-1100-4000-8000-000000000001', true,
    'account-idempotency-key-0001'
  );
  select * into strict v_replay
  from public.set_managed_account_archived(
    '51000000-1000-4000-8000-000000000001',
    '51000000-1100-4000-8000-000000000001', true,
    'account-idempotency-key-0001'
  );

  if to_jsonb(v_first) is distinct from to_jsonb(v_replay) then
    raise exception 'archive replay did not return the exact stored response';
  end if;

  select count(*) into v_rows
  from public.audit_events
  where household_id = '51000000-1000-4000-8000-000000000001'
    and action = 'archived'
    and payload ->> 'idempotency_key' = 'account-idempotency-key-0001';
  if v_rows <> 1 then
    raise exception 'archive replay appended % audit rows instead of 1', v_rows;
  end if;

  begin
    perform * from public.set_managed_account_archived(
      '51000000-1000-4000-8000-000000000001',
      '51000000-1100-4000-8000-000000000001', false,
      'account-idempotency-key-0001'
    );
    raise exception 'archive accepted a reused key with a different payload';
  exception
    when unique_violation then null;
  end;
end;
$$;

do $$
declare
  v_member_id uuid;
  v_original public.transactions;
  v_replay public.transactions;
  v_balance bigint;
begin
  select hm.id into strict v_member_id
  from public.household_members hm
  where hm.household_id = '51000000-1000-4000-8000-000000000001'
    and hm.profile_id = '51000000-0000-4000-8000-000000000001';
  select * into strict v_original
  from public.transactions t
  where t.household_id = '51000000-1000-4000-8000-000000000001'
    and t.idempotency_key = 'archived-replay-income-0001';

  select * into strict v_replay
  from public.confirm_transaction(
    '51000000-1000-4000-8000-000000000001',
    '51000000-1100-4000-8000-000000000001',
    '51000000-1200-4000-8000-000000000001',
    v_member_id,
    'income', 10000, 'INR', '2026-08-09T10:00:00Z'::timestamptz,
    jsonb_build_array(jsonb_build_object(
      'member_id', v_member_id, 'amount_paise', 10000
    )),
    'archived-replay-income-0001', 'Replay salary', null, '{}'::jsonb
  );
  if to_jsonb(v_replay) is distinct from to_jsonb(v_original) then
    raise exception 'exact confirm replay changed after account archival';
  end if;

  begin
    perform * from public.void_transaction(
      '51000000-1000-4000-8000-000000000001',
      v_original.id,
      'Archived account must remain balanced'
    );
    raise exception 'void changed the balance of an archived account';
  exception
    when check_violation then null;
  end;
  if (select status from public.transactions where id = v_original.id) <> 'posted' then
    raise exception 'blocked void changed transaction status';
  end if;
  select b.balance_paise into strict v_balance
  from public.get_account_balances('51000000-1000-4000-8000-000000000001') b
  where b.account_id = '51000000-1100-4000-8000-000000000001';
  if v_balance <> 0 then
    raise exception 'blocked void changed archived account balance to %', v_balance;
  end if;
end;
$$;

reset role;

insert into public.accounts (
  household_id, name, account_type, opening_balance_paise, is_archived
)
select
  '51000000-1000-4000-8000-000000000001',
  'Active Limit ' || item,
  'bank',
  0,
  false
from generate_series(1, 19) item;

insert into public.accounts (
  id, household_id, name, account_type, opening_balance_paise, is_archived
) values (
  '51000000-1100-4000-8000-000000000099',
  '51000000-1000-4000-8000-000000000001',
  'Archived Beyond Limit', 'bank', 0, true
);

set local role authenticated;

do $$
begin
  begin
    perform * from public.set_managed_account_archived(
      '51000000-1000-4000-8000-000000000001',
      '51000000-1100-4000-8000-000000000099',
      false,
      'restore-active-limit-0001'
    );
    raise exception 'restore exceeded the active account limit';
  exception
    when invalid_parameter_value then null;
  end;
end;
$$;

do $$
begin
  begin
    perform * from public.create_managed_account(
      '51000000-1000-4000-8000-000000000001',
      'Null Key Bank', 'bank', 0, null, null, null, null
    );
    raise exception 'create accepted a null idempotency key';
  exception
    when invalid_parameter_value then null;
  end;

  begin
    perform * from public.update_managed_account(
      '51000000-1000-4000-8000-000000000001',
      '51000000-1100-4000-8000-000000000001',
      'Null Key Rename', null, null, null, null
    );
    raise exception 'update accepted a null idempotency key';
  exception
    when invalid_parameter_value then null;
  end;

  begin
    perform * from public.set_managed_account_archived(
      '51000000-1000-4000-8000-000000000001',
      '51000000-1100-4000-8000-000000000001', false, null
    );
    raise exception 'archive accepted a null idempotency key';
  exception
    when invalid_parameter_value then null;
  end;

  begin
    perform * from public.create_balance_adjustment(
      '51000000-1000-4000-8000-000000000001',
      '51000000-1100-4000-8000-000000000001',
      1000, 'Null key must fail', now(), null
    );
    raise exception 'balance adjustment accepted a null idempotency key';
  exception
    when invalid_parameter_value then null;
  end;
end;
$$;

reset role;
rollback;
