-- Run with `supabase test db` after the local stack is available. These catalog
-- assertions need no application secrets. Authenticated/anonymous behavioural
-- RLS tests still require a live Postgres/Supabase runtime and JWT claim setup.
begin;

do $$
declare
  v_missing text;
begin
  select string_agg(required_table, ', ' order by required_table)
  into v_missing
  from unnest(array[
    'accounts', 'audit_events', 'categories', 'household_members', 'households',
    'merchant_rules', 'profiles', 'settlements', 'transaction_splits',
    'transactions', 'transfer_links'
  ]) as required(required_table)
  where not exists (
    select 1
    from pg_catalog.pg_class c
    join pg_catalog.pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relname = required_table
      and c.relrowsecurity
  );

  if v_missing is not null then
    raise exception 'tables missing RLS: %', v_missing;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema = 'public'
      and table_name = 'transactions'
      and column_name = 'paid_by_member_id'
  ) then
    raise exception 'transactions.paid_by_member_id is missing';
  end if;

  if (
    select count(*)
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'accounts'
      and column_name in ('credit_limit_paise', 'statement_day', 'payment_due_day')
  ) <> 3 then
    raise exception 'credit-card onboarding columns are missing';
  end if;

  if not exists (
    select 1 from pg_catalog.pg_proc p
    join pg_catalog.pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname = 'confirm_transaction'
  ) or not exists (
    select 1 from pg_catalog.pg_proc p
    join pg_catalog.pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname = 'create_transfer'
  ) or not exists (
    select 1 from pg_catalog.pg_proc p
    join pg_catalog.pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname = 'create_settlement'
  ) then
    raise exception 'required atomic ledger RPC is missing';
  end if;

  if exists (
    select 1 from pg_catalog.pg_policies
    where schemaname = 'public'
      and tablename in (
        'transactions', 'transaction_splits', 'transfer_links', 'settlements', 'audit_events'
      )
      and cmd in ('INSERT', 'UPDATE', 'DELETE', 'ALL')
  ) then
    raise exception 'append-only ledger table has a direct client mutation policy';
  end if;
end;
$$;

rollback;
