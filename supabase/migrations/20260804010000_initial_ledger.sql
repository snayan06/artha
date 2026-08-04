-- Artha V1 production ledger schema.
-- Security boundary: clients use the authenticated role and RLS. The service_role
-- is intentionally reserved for trusted server operations and Supabase maintenance.

create schema if not exists private;
revoke all on schema private from public;
grant usage on schema private to authenticated;

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text not null check (char_length(trim(display_name)) between 1 and 100),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.households (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(trim(name)) between 1 and 100),
  created_by uuid not null references public.profiles (id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.household_members (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references public.households (id) on delete cascade,
  profile_id uuid references public.profiles (id) on delete restrict,
  display_name text not null check (char_length(trim(display_name)) between 1 and 100),
  member_type text not null check (member_type in ('user', 'participant')),
  role text not null default 'member' check (role in ('owner', 'member')),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint household_members_type_profile_ck check (
    (member_type = 'user' and profile_id is not null)
    or (member_type = 'participant' and profile_id is null)
  ),
  constraint household_members_owner_is_user_ck check (
    role <> 'owner' or member_type = 'user'
  ),
  constraint household_members_household_id_id_key unique (household_id, id)
);

create unique index household_members_one_profile_per_household_idx
  on public.household_members (household_id, profile_id)
  where profile_id is not null;
create index household_members_profile_idx
  on public.household_members (profile_id, household_id)
  where profile_id is not null and is_active;

create table public.accounts (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references public.households (id) on delete cascade,
  name text not null check (char_length(trim(name)) between 1 and 100),
  account_type text not null check (account_type in ('cash', 'bank', 'wallet', 'credit_card', 'other')),
  currency text not null default 'INR' check (currency ~ '^[A-Z]{3}$'),
  opening_balance_paise bigint not null default 0,
  credit_limit_paise bigint check (credit_limit_paise is null or credit_limit_paise >= 0),
  is_archived boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint accounts_household_id_id_key unique (household_id, id)
);

create unique index accounts_unique_active_name_idx
  on public.accounts (household_id, lower(name))
  where not is_archived;

create table public.categories (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references public.households (id) on delete cascade,
  name text not null check (char_length(trim(name)) between 1 and 80),
  category_type text not null check (category_type in ('expense', 'income', 'both')),
  icon text,
  is_archived boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint categories_household_id_id_key unique (household_id, id)
);

create unique index categories_unique_active_name_idx
  on public.categories (household_id, lower(name))
  where not is_archived;

create table public.transactions (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references public.households (id) on delete cascade,
  account_id uuid not null,
  category_id uuid,
  direction text not null check (
    direction in ('expense', 'income', 'transfer_out', 'transfer_in', 'settlement_out', 'settlement_in')
  ),
  amount_paise bigint not null check (amount_paise > 0),
  currency text not null default 'INR' check (currency ~ '^[A-Z]{3}$'),
  occurred_at timestamptz not null,
  merchant text check (merchant is null or char_length(trim(merchant)) between 1 and 160),
  note text check (note is null or char_length(note) <= 1000),
  status text not null default 'posted' check (status in ('posted', 'voided')),
  idempotency_key text check (
    idempotency_key is null or char_length(idempotency_key) between 8 and 200
  ),
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_by uuid not null references public.profiles (id) on delete restrict,
  created_at timestamptz not null default now(),
  voided_at timestamptz,
  constraint transactions_household_account_fk
    foreign key (household_id, account_id)
    references public.accounts (household_id, id) on delete restrict,
  constraint transactions_household_category_fk
    foreign key (household_id, category_id)
    references public.categories (household_id, id) on delete restrict,
  constraint transactions_category_direction_ck check (
    (direction in ('expense', 'income') and category_id is not null)
    or (direction not in ('expense', 'income') and category_id is null)
  ),
  constraint transactions_void_state_ck check (
    (status = 'posted' and voided_at is null)
    or (status = 'voided' and voided_at is not null)
  ),
  constraint transactions_household_id_id_key unique (household_id, id)
);

create unique index transactions_idempotency_idx
  on public.transactions (household_id, created_by, idempotency_key)
  where idempotency_key is not null;
create index transactions_household_occurred_idx
  on public.transactions (household_id, occurred_at desc, id desc);
create index transactions_account_occurred_idx
  on public.transactions (account_id, occurred_at desc)
  where status = 'posted';
create index transactions_category_occurred_idx
  on public.transactions (category_id, occurred_at desc)
  where status = 'posted' and category_id is not null;

create table public.transaction_splits (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null,
  transaction_id uuid not null,
  member_id uuid not null,
  amount_paise bigint not null check (amount_paise > 0),
  created_at timestamptz not null default now(),
  constraint transaction_splits_household_transaction_fk
    foreign key (household_id, transaction_id)
    references public.transactions (household_id, id) on delete cascade,
  constraint transaction_splits_household_member_fk
    foreign key (household_id, member_id)
    references public.household_members (household_id, id) on delete restrict,
  constraint transaction_splits_one_member_key unique (transaction_id, member_id)
);

create index transaction_splits_member_idx
  on public.transaction_splits (household_id, member_id, transaction_id);

create table public.settlements (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references public.households (id) on delete cascade,
  payer_member_id uuid not null,
  payee_member_id uuid not null,
  amount_paise bigint not null check (amount_paise > 0),
  currency text not null default 'INR' check (currency ~ '^[A-Z]{3}$'),
  settled_at timestamptz not null,
  note text check (note is null or char_length(note) <= 1000),
  created_by uuid not null references public.profiles (id) on delete restrict,
  created_at timestamptz not null default now(),
  constraint settlements_distinct_members_ck check (payer_member_id <> payee_member_id),
  constraint settlements_household_payer_fk
    foreign key (household_id, payer_member_id)
    references public.household_members (household_id, id) on delete restrict,
  constraint settlements_household_payee_fk
    foreign key (household_id, payee_member_id)
    references public.household_members (household_id, id) on delete restrict
);

create index settlements_household_date_idx
  on public.settlements (household_id, settled_at desc);

create table public.transfer_links (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references public.households (id) on delete cascade,
  transfer_out_transaction_id uuid not null,
  transfer_in_transaction_id uuid not null,
  created_at timestamptz not null default now(),
  constraint transfer_links_distinct_transactions_ck
    check (transfer_out_transaction_id <> transfer_in_transaction_id),
  constraint transfer_links_household_out_fk
    foreign key (household_id, transfer_out_transaction_id)
    references public.transactions (household_id, id) on delete cascade,
  constraint transfer_links_household_in_fk
    foreign key (household_id, transfer_in_transaction_id)
    references public.transactions (household_id, id) on delete cascade,
  constraint transfer_links_out_unique unique (transfer_out_transaction_id),
  constraint transfer_links_in_unique unique (transfer_in_transaction_id)
);

create table public.merchant_rules (
  id uuid primary key default gen_random_uuid(),
  household_id uuid not null references public.households (id) on delete cascade,
  match_type text not null default 'contains' check (match_type in ('exact', 'contains', 'regex')),
  merchant_pattern text not null check (char_length(trim(merchant_pattern)) between 1 and 160),
  category_id uuid not null,
  account_id uuid,
  priority integer not null default 100 check (priority between 0 and 10000),
  is_active boolean not null default true,
  created_by uuid not null references public.profiles (id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint merchant_rules_household_category_fk
    foreign key (household_id, category_id)
    references public.categories (household_id, id) on delete cascade,
  constraint merchant_rules_household_account_fk
    foreign key (household_id, account_id)
    references public.accounts (household_id, id) on delete cascade
);

create index merchant_rules_lookup_idx
  on public.merchant_rules (household_id, is_active, priority, id);

create table public.audit_events (
  id bigint generated always as identity primary key,
  household_id uuid not null references public.households (id) on delete cascade,
  actor_profile_id uuid references public.profiles (id) on delete set null,
  entity_type text not null check (entity_type ~ '^[a-z][a-z0-9_]{1,49}$'),
  entity_id uuid,
  action text not null check (action ~ '^[a-z][a-z0-9_]{1,49}$'),
  payload jsonb not null default '{}'::jsonb check (jsonb_typeof(payload) = 'object'),
  occurred_at timestamptz not null default now()
);

create index audit_events_household_time_idx
  on public.audit_events (household_id, occurred_at desc, id desc);

-- SECURITY DEFINER helpers keep RLS policy evaluation non-recursive. They expose
-- only boolean membership decisions and are not in an API-exposed schema.
create or replace function private.is_household_member(p_household_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
set row_security = off
as $$
  select exists (
    select 1
    from public.household_members hm
    where hm.household_id = p_household_id
      and hm.profile_id = auth.uid()
      and hm.is_active
  );
$$;

create or replace function private.is_household_owner(p_household_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
set row_security = off
as $$
  select exists (
    select 1
    from public.household_members hm
    where hm.household_id = p_household_id
      and hm.profile_id = auth.uid()
      and hm.role = 'owner'
      and hm.is_active
  );
$$;

revoke all on function private.is_household_member(uuid) from public;
revoke all on function private.is_household_owner(uuid) from public;
grant execute on function private.is_household_member(uuid) to authenticated;
grant execute on function private.is_household_owner(uuid) to authenticated;

create or replace function private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create trigger profiles_set_updated_at
before update on public.profiles
for each row execute function private.set_updated_at();
create trigger households_set_updated_at
before update on public.households
for each row execute function private.set_updated_at();
create trigger household_members_set_updated_at
before update on public.household_members
for each row execute function private.set_updated_at();
create trigger accounts_set_updated_at
before update on public.accounts
for each row execute function private.set_updated_at();
create trigger categories_set_updated_at
before update on public.categories
for each row execute function private.set_updated_at();
create trigger merchant_rules_set_updated_at
before update on public.merchant_rules
for each row execute function private.set_updated_at();

create or replace function private.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, display_name)
  values (
    new.id,
    coalesce(
      nullif(trim(new.raw_user_meta_data ->> 'display_name'), ''),
      nullif(trim(new.raw_user_meta_data ->> 'full_name'), ''),
      split_part(coalesce(new.email, 'Artha user'), '@', 1)
    )
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users
for each row execute function private.handle_new_auth_user();

create or replace function private.add_household_creator()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_display_name text;
begin
  select p.display_name into strict v_display_name
  from public.profiles p
  where p.id = new.created_by;

  insert into public.household_members (
    household_id, profile_id, display_name, member_type, role
  ) values (
    new.id, new.created_by, v_display_name, 'user', 'owner'
  );
  return new;
end;
$$;

create trigger households_add_creator
after insert on public.households
for each row execute function private.add_household_creator();

create or replace function private.validate_transfer_link()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_out public.transactions;
  v_in public.transactions;
begin
  select * into strict v_out
  from public.transactions
  where household_id = new.household_id and id = new.transfer_out_transaction_id;

  select * into strict v_in
  from public.transactions
  where household_id = new.household_id and id = new.transfer_in_transaction_id;

  if v_out.direction <> 'transfer_out' or v_in.direction <> 'transfer_in' then
    raise exception 'transfer link requires transfer_out and transfer_in transactions'
      using errcode = '23514';
  end if;
  if v_out.amount_paise <> v_in.amount_paise or v_out.currency <> v_in.currency then
    raise exception 'linked transfer amount and currency must match'
      using errcode = '23514';
  end if;
  if v_out.status <> v_in.status then
    raise exception 'linked transfer status must match'
      using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger transfer_links_validate
before insert or update on public.transfer_links
for each row execute function private.validate_transfer_link();

alter table public.profiles enable row level security;
alter table public.households enable row level security;
alter table public.household_members enable row level security;
alter table public.accounts enable row level security;
alter table public.categories enable row level security;
alter table public.transactions enable row level security;
alter table public.transaction_splits enable row level security;
alter table public.settlements enable row level security;
alter table public.transfer_links enable row level security;
alter table public.merchant_rules enable row level security;
alter table public.audit_events enable row level security;

create policy profiles_select_self on public.profiles
  for select to authenticated using (id = auth.uid());
create policy profiles_update_self on public.profiles
  for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

create policy households_select_member on public.households
  for select to authenticated using (private.is_household_member(id));
create policy households_insert_self on public.households
  for insert to authenticated with check (created_by = auth.uid());
create policy households_update_owner on public.households
  for update to authenticated using (private.is_household_owner(id))
  with check (private.is_household_owner(id) and created_by = auth.uid());
create policy households_delete_owner on public.households
  for delete to authenticated using (private.is_household_owner(id));

create policy household_members_select_member on public.household_members
  for select to authenticated using (private.is_household_member(household_id));
create policy household_members_insert_owner on public.household_members
  for insert to authenticated with check (private.is_household_owner(household_id));
create policy household_members_update_owner on public.household_members
  for update to authenticated using (private.is_household_owner(household_id))
  with check (private.is_household_owner(household_id));
create policy household_members_delete_owner on public.household_members
  for delete to authenticated using (private.is_household_owner(household_id));

create policy accounts_select_member on public.accounts
  for select to authenticated using (private.is_household_member(household_id));
create policy accounts_insert_member on public.accounts
  for insert to authenticated with check (private.is_household_member(household_id));
create policy accounts_update_member on public.accounts
  for update to authenticated using (private.is_household_member(household_id))
  with check (private.is_household_member(household_id));

create policy categories_select_member on public.categories
  for select to authenticated using (private.is_household_member(household_id));
create policy categories_insert_member on public.categories
  for insert to authenticated with check (private.is_household_member(household_id));
create policy categories_update_member on public.categories
  for update to authenticated using (private.is_household_member(household_id))
  with check (private.is_household_member(household_id));

-- Ledger rows are append-only from clients. Mutations happen through validated,
-- atomic RPCs below; no INSERT/UPDATE/DELETE policies are intentionally present.
create policy transactions_select_member on public.transactions
  for select to authenticated using (private.is_household_member(household_id));
create policy transaction_splits_select_member on public.transaction_splits
  for select to authenticated using (private.is_household_member(household_id));
create policy transfer_links_select_member on public.transfer_links
  for select to authenticated using (private.is_household_member(household_id));

create policy settlements_select_member on public.settlements
  for select to authenticated using (private.is_household_member(household_id));
create policy settlements_insert_member on public.settlements
  for insert to authenticated with check (
    private.is_household_member(household_id) and created_by = auth.uid()
  );

create policy merchant_rules_select_member on public.merchant_rules
  for select to authenticated using (private.is_household_member(household_id));
create policy merchant_rules_insert_member on public.merchant_rules
  for insert to authenticated with check (
    private.is_household_member(household_id) and created_by = auth.uid()
  );
create policy merchant_rules_update_member on public.merchant_rules
  for update to authenticated using (private.is_household_member(household_id))
  with check (private.is_household_member(household_id) and created_by = auth.uid());
create policy merchant_rules_delete_member on public.merchant_rules
  for delete to authenticated using (private.is_household_member(household_id));

-- Audit events are visible to household members but append-only to trusted RPCs.
create policy audit_events_select_member on public.audit_events
  for select to authenticated using (private.is_household_member(household_id));

-- Explicit confirmation boundary. The browser/API sends the reviewed draft once;
-- this function validates and posts the transaction plus all splits atomically.
create or replace function public.confirm_transaction(
  p_household_id uuid,
  p_account_id uuid,
  p_category_id uuid,
  p_direction text,
  p_amount_paise bigint,
  p_currency text,
  p_occurred_at timestamptz,
  p_splits jsonb,
  p_merchant text default null,
  p_note text default null,
  p_idempotency_key text default null,
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
  v_split_count integer;
  v_split_total numeric;
begin
  if auth.uid() is null or not private.is_household_member(p_household_id) then
    raise exception 'not authorized for household' using errcode = '42501';
  end if;
  if p_direction not in ('expense', 'income') then
    raise exception 'confirmation supports expense or income only' using errcode = '22023';
  end if;
  if p_amount_paise is null or p_amount_paise <= 0 then
    raise exception 'amount_paise must be a positive integer' using errcode = '22023';
  end if;
  if p_currency is null or p_currency !~ '^[A-Z]{3}$' then
    raise exception 'currency must be an ISO 4217 code' using errcode = '22023';
  end if;
  if not exists (
    select 1
    from public.accounts a
    where a.household_id = p_household_id
      and a.id = p_account_id
      and a.currency = p_currency
      and not a.is_archived
  ) then
    raise exception 'account must be active, in the household, and use the transaction currency'
      using errcode = '23514';
  end if;
  if not exists (
    select 1
    from public.categories c
    where c.household_id = p_household_id
      and c.id = p_category_id
      and c.category_type in (p_direction, 'both')
      and not c.is_archived
  ) then
    raise exception 'category must be active and compatible with transaction direction'
      using errcode = '23514';
  end if;
  if jsonb_typeof(p_splits) <> 'array' or jsonb_array_length(p_splits) = 0 then
    raise exception 'splits must be a non-empty JSON array' using errcode = '22023';
  end if;

  select count(*), coalesce(sum((s.value ->> 'amount_paise')::bigint), 0)
  into v_split_count, v_split_total
  from jsonb_array_elements(p_splits) s(value);

  if v_split_total <> p_amount_paise then
    raise exception 'split total must equal transaction amount' using errcode = '23514';
  end if;
  if exists (
    select 1
    from jsonb_array_elements(p_splits) s(value)
    where (s.value ->> 'amount_paise')::bigint <= 0
       or not exists (
         select 1 from public.household_members hm
         where hm.household_id = p_household_id
           and hm.id = (s.value ->> 'member_id')::uuid
           and hm.is_active
       )
  ) then
    raise exception 'every split must reference an active household member and be positive'
      using errcode = '23514';
  end if;
  if (
    select count(distinct (s.value ->> 'member_id')::uuid)
    from jsonb_array_elements(p_splits) s(value)
  ) <> v_split_count then
    raise exception 'a member may appear only once in splits' using errcode = '23505';
  end if;

  insert into public.transactions (
    household_id, account_id, category_id, direction, amount_paise, currency,
    occurred_at, merchant, note, idempotency_key, metadata, created_by
  ) values (
    p_household_id, p_account_id, p_category_id, p_direction, p_amount_paise,
    p_currency, p_occurred_at, nullif(trim(p_merchant), ''), p_note,
    p_idempotency_key, p_metadata, auth.uid()
  )
  returning * into v_transaction;

  insert into public.transaction_splits (
    household_id, transaction_id, member_id, amount_paise
  )
  select
    p_household_id,
    v_transaction.id,
    (s.value ->> 'member_id')::uuid,
    (s.value ->> 'amount_paise')::bigint
  from jsonb_array_elements(p_splits) s(value);

  insert into public.audit_events (
    household_id, actor_profile_id, entity_type, entity_id, action, payload
  ) values (
    p_household_id,
    auth.uid(),
    'transaction',
    v_transaction.id,
    'confirmed',
    jsonb_build_object('amount_paise', p_amount_paise, 'direction', p_direction)
  );

  return v_transaction;
end;
$$;

revoke all on function public.confirm_transaction(
  uuid, uuid, uuid, text, bigint, text, timestamptz, jsonb, text, text, text, jsonb
) from public, anon;
grant execute on function public.confirm_transaction(
  uuid, uuid, uuid, text, bigint, text, timestamptz, jsonb, text, text, text, jsonb
) to authenticated;

-- Safe read RPC: the function re-checks membership and returns only household
-- account aggregates. It never accepts an arbitrary profile/user identifier.
create or replace function public.get_account_balances(p_household_id uuid)
returns table (
  account_id uuid,
  account_name text,
  currency text,
  balance_paise bigint
)
language plpgsql
stable
security definer
set search_path = ''
set row_security = off
as $$
begin
  if auth.uid() is null or not private.is_household_member(p_household_id) then
    raise exception 'not authorized for household' using errcode = '42501';
  end if;

  return query
  select
    a.id,
    a.name,
    a.currency,
    a.opening_balance_paise + coalesce(sum(
      case t.direction
        when 'income' then t.amount_paise
        when 'transfer_in' then t.amount_paise
        when 'settlement_in' then t.amount_paise
        when 'expense' then -t.amount_paise
        when 'transfer_out' then -t.amount_paise
        when 'settlement_out' then -t.amount_paise
      end
    ) filter (where t.status = 'posted'), 0)::bigint
  from public.accounts a
  left join public.transactions t on t.account_id = a.id
  where a.household_id = p_household_id
  group by a.id, a.name, a.currency, a.opening_balance_paise
  order by a.name, a.id;
end;
$$;

revoke all on function public.get_account_balances(uuid) from public, anon;
grant execute on function public.get_account_balances(uuid) to authenticated;

-- Keep new objects least-privileged if this migration is extended later.
alter default privileges in schema public revoke all on tables from anon;
alter default privileges in schema public revoke all on functions from public, anon;
