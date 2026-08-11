-- Exact evidence drill-down must return one canonical logical movement without
-- allowing cross-household or anonymous access. Fictional rows roll back.
begin;

do $$
declare
  v_function regprocedure := to_regprocedure(
    'public.get_ledger_activity(uuid,uuid)'
  );
begin
  if v_function is null then
    raise exception 'get_ledger_activity RPC is missing';
  end if;
  if not exists (
    select 1
    from pg_catalog.pg_proc p
    where p.oid = v_function
      and p.prosecdef
      and p.provolatile = 's'
      and coalesce(array_to_string(p.proconfig, ','), '') like '%search_path=%'
      and coalesce(array_to_string(p.proconfig, ','), '') like '%row_security=off%'
  ) then
    raise exception 'get_ledger_activity RPC is not hardened and stable';
  end if;
  if not has_function_privilege('authenticated', v_function, 'EXECUTE')
     or has_function_privilege('anon', v_function, 'EXECUTE')
     or has_function_privilege('service_role', v_function, 'EXECUTE') then
    raise exception 'get_ledger_activity RPC privileges are unsafe';
  end if;
end;
$$;

insert into auth.users (
  id, aud, role, email, encrypted_password, email_confirmed_at,
  raw_app_meta_data, raw_user_meta_data, created_at, updated_at
) values
  (
    '81000000-0000-4000-8000-000000000001',
    'authenticated', 'authenticated', 'detail-a@example.test', '', now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Detail Owner A"}'::jsonb, now(), now()
  ),
  (
    '82000000-0000-4000-8000-000000000002',
    'authenticated', 'authenticated', 'detail-b@example.test', '', now(),
    '{"provider":"email","providers":["email"]}'::jsonb,
    '{"display_name":"Detail Owner B"}'::jsonb, now(), now()
  );

insert into public.households (id, name, created_by) values
  (
    '81000000-1000-4000-8000-000000000001', 'Detail Household A',
    '81000000-0000-4000-8000-000000000001'
  ),
  (
    '82000000-2000-4000-8000-000000000002', 'Detail Household B',
    '82000000-0000-4000-8000-000000000002'
  );

insert into public.accounts (
  id, household_id, name, account_type, opening_balance_paise
) values
  (
    '81000000-1100-4000-8000-000000000001',
    '81000000-1000-4000-8000-000000000001', 'Detail Bank A', 'bank', 100000
  ),
  (
    '82000000-2200-4000-8000-000000000002',
    '82000000-2000-4000-8000-000000000002', 'Detail Bank B', 'bank', 100000
  );

insert into public.categories (id, household_id, name, category_type) values
  (
    '81000000-1200-4000-8000-000000000001',
    '81000000-1000-4000-8000-000000000001', 'Detail Food A', 'expense'
  ),
  (
    '82000000-2300-4000-8000-000000000002',
    '82000000-2000-4000-8000-000000000002', 'Detail Food B', 'expense'
  );

set local role authenticated;
select set_config(
  'request.jwt.claim.sub', '81000000-0000-4000-8000-000000000001', true
);
select set_config('request.jwt.claim.role', 'authenticated', true);

do $$
declare
  v_owner_id uuid;
  v_activity_id uuid;
  v_detail jsonb;
begin
  select hm.id into strict v_owner_id
  from public.household_members hm
  where hm.household_id = '81000000-1000-4000-8000-000000000001'
    and hm.profile_id = '81000000-0000-4000-8000-000000000001';

  select result.id into strict v_activity_id
  from public.confirm_transaction(
    '81000000-1000-4000-8000-000000000001',
    '81000000-1100-4000-8000-000000000001',
    '81000000-1200-4000-8000-000000000001',
    v_owner_id,
    'expense', 18400, 'INR', '2026-08-11T10:00:00Z'::timestamptz,
    jsonb_build_array(jsonb_build_object(
      'member_id', v_owner_id, 'amount_paise', 18400
    )),
    'detail-activity-a-0001', 'Detail Zomato', null, '{}'::jsonb
  ) result;

  v_detail := public.get_ledger_activity(
    '81000000-1000-4000-8000-000000000001', v_activity_id
  );
  if v_detail ->> 'id' <> v_activity_id::text
     or v_detail ->> 'description' <> 'Detail Zomato'
     or v_detail ->> 'kind' <> 'expense'
     or (v_detail ->> 'personal_share_paise')::bigint <> 18400 then
    raise exception 'exact detail did not return the canonical activity: %', v_detail;
  end if;

  if public.get_ledger_activity(
    '81000000-1000-4000-8000-000000000001',
    '81000000-9900-4000-8000-000000000099'
  ) is not null then
    raise exception 'unknown activity returned a result';
  end if;
end;
$$;

select set_config(
  'request.jwt.claim.sub', '82000000-0000-4000-8000-000000000002', true
);

do $$
declare
  v_owner_id uuid;
  v_activity_id uuid;
begin
  select hm.id into strict v_owner_id
  from public.household_members hm
  where hm.household_id = '82000000-2000-4000-8000-000000000002'
    and hm.profile_id = '82000000-0000-4000-8000-000000000002';

  select result.id into strict v_activity_id
  from public.confirm_transaction(
    '82000000-2000-4000-8000-000000000002',
    '82000000-2200-4000-8000-000000000002',
    '82000000-2300-4000-8000-000000000002',
    v_owner_id,
    'expense', 25000, 'INR', '2026-08-11T11:00:00Z'::timestamptz,
    jsonb_build_array(jsonb_build_object(
      'member_id', v_owner_id, 'amount_paise', 25000
    )),
    'detail-activity-b-0001', 'Private B purchase', null, '{}'::jsonb
  ) result;

  perform set_config(
    'request.jwt.claim.sub', '81000000-0000-4000-8000-000000000001', true
  );
  if public.get_ledger_activity(
    '81000000-1000-4000-8000-000000000001', v_activity_id
  ) is not null then
    raise exception 'owner A resolved owner B activity through household A';
  end if;

  begin
    perform public.get_ledger_activity(
      '82000000-2000-4000-8000-000000000002', v_activity_id
    );
    raise exception 'owner A resolved owner B activity through household B';
  exception
    when insufficient_privilege then null;
  end;
end;
$$;

reset role;
rollback;
