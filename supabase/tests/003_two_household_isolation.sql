-- Behavioral two-household RLS acceptance. `supabase test db` runs this inside
-- one transaction after applying every migration; all fictional rows roll back.
begin;

insert into auth.users (
  id, aud, role, email, encrypted_password, email_confirmed_at,
  raw_app_meta_data, raw_user_meta_data, created_at, updated_at
) values
  (
    '10000000-0000-4000-8000-000000000001',
    'authenticated', 'authenticated', 'rls-a@example.test', '', now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"RLS User A"}'::jsonb, now(), now()
  ),
  (
    '20000000-0000-4000-8000-000000000002',
    'authenticated', 'authenticated', 'rls-b@example.test', '', now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"RLS User B"}'::jsonb, now(), now()
  );

insert into public.households (id, name, created_by) values
  (
    '10000000-1000-4000-8000-000000000001', 'RLS Household A',
    '10000000-0000-4000-8000-000000000001'
  ),
  (
    '20000000-2000-4000-8000-000000000002', 'RLS Household B',
    '20000000-0000-4000-8000-000000000002'
  );

insert into public.accounts (
  id, household_id, name, account_type, opening_balance_paise
) values
  (
    '10000000-1100-4000-8000-000000000001',
    '10000000-1000-4000-8000-000000000001',
    'RLS Bank A', 'bank', 100000
  ),
  (
    '20000000-2200-4000-8000-000000000002',
    '20000000-2000-4000-8000-000000000002',
    'RLS Bank B', 'bank', 200000
  );

insert into public.categories (id, household_id, name, category_type) values
  (
    '10000000-1200-4000-8000-000000000001',
    '10000000-1000-4000-8000-000000000001',
    'RLS Category A', 'expense'
  ),
  (
    '20000000-2300-4000-8000-000000000002',
    '20000000-2000-4000-8000-000000000002',
    'RLS Category B', 'expense'
  );

set local role authenticated;
select set_config(
  'request.jwt.claim.sub', '10000000-0000-4000-8000-000000000001', true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

do $$
declare
  v_rows integer;
  v_household uuid;
begin
  select count(*) into v_rows from public.profiles;
  if v_rows <> 1 or not exists (
    select 1 from public.profiles
    where id = '10000000-0000-4000-8000-000000000001'
  ) then
    raise exception 'user A must see only its own profile';
  end if;

  select count(*) into v_rows from public.households;
  if v_rows <> 1 or exists (
    select 1 from public.households
    where id = '20000000-2000-4000-8000-000000000002'
  ) then
    raise exception 'user A can see household B';
  end if;

  select count(*) into v_rows from public.household_members;
  if v_rows <> 1 or exists (
    select 1 from public.household_members
    where household_id = '20000000-2000-4000-8000-000000000002'
  ) then
    raise exception 'user A can see household B members';
  end if;

  select count(*) into v_rows from public.accounts;
  if v_rows <> 1 or exists (
    select 1 from public.accounts
    where id = '20000000-2200-4000-8000-000000000002'
  ) then
    raise exception 'user A can see household B accounts';
  end if;

  select public.get_current_household() into v_household;
  if v_household <> '10000000-1000-4000-8000-000000000001' then
    raise exception 'user A current household is incorrect: %', v_household;
  end if;

  insert into public.merchant_rules (
    household_id, merchant_pattern, category_id, account_id, created_by
  ) values (
    '10000000-1000-4000-8000-000000000001',
    'RLS User A Own Rule',
    '10000000-1200-4000-8000-000000000001',
    '10000000-1100-4000-8000-000000000001',
    '10000000-0000-4000-8000-000000000001'
  );

  begin
    insert into public.merchant_rules (
      household_id, merchant_pattern, category_id, account_id, created_by
    ) values (
      '20000000-2000-4000-8000-000000000002',
      'RLS Cross Rule Must Fail',
      '20000000-2300-4000-8000-000000000002',
      '20000000-2200-4000-8000-000000000002',
      '10000000-0000-4000-8000-000000000001'
    );
    raise exception 'user A inserted a rule into household B';
  exception
    when insufficient_privilege then null;
  end;

  update public.merchant_rules
  set merchant_pattern = 'RLS Cross Update Must Not Apply'
  where household_id = '20000000-2000-4000-8000-000000000002';
  get diagnostics v_rows = row_count;
  if v_rows <> 0 then
    raise exception 'user A updated a rule in household B';
  end if;

  begin
    perform * from public.get_account_balances(
      '20000000-2000-4000-8000-000000000002'
    );
    raise exception 'user A called a balance RPC for household B';
  exception
    when insufficient_privilege then null;
  end;
end;
$$;

select set_config(
  'request.jwt.claim.sub', '20000000-0000-4000-8000-000000000002', true
);

do $$
declare
  v_rows integer;
  v_household uuid;
begin
  select count(*) into v_rows from public.profiles;
  if v_rows <> 1 or not exists (
    select 1 from public.profiles
    where id = '20000000-0000-4000-8000-000000000002'
  ) then
    raise exception 'user B must see only its own profile';
  end if;

  select count(*) into v_rows from public.households;
  if v_rows <> 1 or exists (
    select 1 from public.households
    where id = '10000000-1000-4000-8000-000000000001'
  ) then
    raise exception 'user B can see household A';
  end if;

  select count(*) into v_rows from public.accounts;
  if v_rows <> 1 or exists (
    select 1 from public.accounts
    where id = '10000000-1100-4000-8000-000000000001'
  ) then
    raise exception 'user B can see household A accounts';
  end if;

  select public.get_current_household() into v_household;
  if v_household <> '20000000-2000-4000-8000-000000000002' then
    raise exception 'user B current household is incorrect: %', v_household;
  end if;

  begin
    perform * from public.get_account_balances(
      '10000000-1000-4000-8000-000000000001'
    );
    raise exception 'user B called a balance RPC for household A';
  exception
    when insufficient_privilege then null;
  end;
end;
$$;

reset role;
set local role anon;
select set_config('request.jwt.claim.sub', '', true);
select set_config('request.jwt.claim.role', 'anon', true);

do $$
begin
  begin
    perform * from public.accounts;
    raise exception 'anon read public.accounts';
  exception
    when insufficient_privilege then null;
  end;
end;
$$;

reset role;
rollback;
