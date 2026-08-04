-- Fictional local-development seed only. It is deliberately a no-op unless a
-- local Auth user with this reserved demo address already exists.
do $$
declare
  v_profile_id uuid;
  v_household_id uuid := '10000000-0000-4000-8000-000000000001';
  v_owner_member_id uuid := '20000000-0000-4000-8000-000000000001';
begin
  select id into v_profile_id
  from auth.users
  where email = 'demo@artha.local';

  if v_profile_id is null then
    raise notice 'Skipping fictional seed: create demo@artha.local in local Auth first';
    return;
  end if;

  insert into public.profiles (id, display_name)
  values (v_profile_id, 'Demo User')
  on conflict (id) do update set display_name = excluded.display_name;

  insert into public.households (id, name, created_by)
  values (v_household_id, 'Demo Home', v_profile_id)
  on conflict (id) do nothing;

  select id into v_owner_member_id
  from public.household_members
  where household_id = v_household_id and profile_id = v_profile_id;

  insert into public.household_members (
    id, household_id, profile_id, display_name, member_type, role
  ) values (
    '20000000-0000-4000-8000-000000000002',
    v_household_id,
    null,
    'Demo Member',
    'participant',
    'member'
  ) on conflict (id) do nothing;

  insert into public.accounts (
    id, household_id, name, account_type, currency, opening_balance_paise
  ) values
    ('30000000-0000-4000-8000-000000000001', v_household_id, 'Demo Bank', 'bank', 'INR', 2500000),
    ('30000000-0000-4000-8000-000000000002', v_household_id, 'Demo Wallet', 'wallet', 'INR', 100000)
  on conflict (id) do nothing;

  insert into public.categories (id, household_id, name, category_type, icon)
  values
    ('40000000-0000-4000-8000-000000000001', v_household_id, 'Groceries', 'expense', 'basket'),
    ('40000000-0000-4000-8000-000000000002', v_household_id, 'Salary', 'income', 'briefcase')
  on conflict (id) do nothing;
end;
$$;
