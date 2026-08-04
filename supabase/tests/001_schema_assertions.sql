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

  if (
    select count(*)
    from information_schema.columns
    where table_schema = 'public'
      and data_type = 'bigint'
      and (table_name, column_name) in (
        ('accounts', 'opening_balance_paise'),
        ('accounts', 'credit_limit_paise'),
        ('transactions', 'amount_paise'),
        ('transaction_splits', 'amount_paise'),
        ('settlements', 'amount_paise')
      )
  ) <> 5 then
    raise exception 'money columns must remain bigint integer paise';
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

  if to_regprocedure('public.get_current_household()') is null
     or to_regprocedure('public.setup_household(text,text,jsonb,jsonb)') is null
     or to_regprocedure('public.void_transaction(uuid,uuid,text)') is null then
    raise exception 'production safety RPC is missing';
  end if;

  if exists (
    select 1
    from pg_catalog.pg_proc p
    where p.oid in (
      to_regprocedure('public.get_current_household()'),
      to_regprocedure('public.setup_household(text,text,jsonb,jsonb)'),
      to_regprocedure('public.void_transaction(uuid,uuid,text)')
    )
      and (
        not p.prosecdef
        or coalesce(array_to_string(p.proconfig, ','), '') not like '%search_path=%'
        or coalesce(array_to_string(p.proconfig, ','), '') not like '%row_security=off%'
      )
  ) then
    raise exception 'production safety RPC must be SECURITY DEFINER with hardened settings';
  end if;

  if (
    select p.provolatile
    from pg_catalog.pg_proc p
    where p.oid = to_regprocedure('public.get_current_household()')
  ) <> 's' then
    raise exception 'get_current_household must be stable';
  end if;

  if not has_function_privilege(
    'authenticated', 'public.get_current_household()', 'EXECUTE'
  ) or not has_function_privilege(
    'authenticated', 'public.setup_household(text,text,jsonb,jsonb)', 'EXECUTE'
  ) or not has_function_privilege(
    'authenticated', 'public.void_transaction(uuid,uuid,text)', 'EXECUTE'
  ) then
    raise exception 'authenticated role is missing production safety RPC execute grant';
  end if;

  if has_function_privilege('anon', 'public.get_current_household()', 'EXECUTE')
     or has_function_privilege(
       'anon', 'public.setup_household(text,text,jsonb,jsonb)', 'EXECUTE'
     )
     or has_function_privilege(
       'anon', 'public.void_transaction(uuid,uuid,text)', 'EXECUTE'
     )
     or has_function_privilege(
       'service_role', 'public.get_current_household()', 'EXECUTE'
     )
     or has_function_privilege(
       'service_role', 'public.setup_household(text,text,jsonb,jsonb)', 'EXECUTE'
     )
     or has_function_privilege(
       'service_role', 'public.void_transaction(uuid,uuid,text)', 'EXECUTE'
     ) then
    raise exception 'production safety RPC leaked execute privilege';
  end if;

  if not exists (
    select 1
    from pg_catalog.pg_trigger t
    join pg_catalog.pg_class c on c.oid = t.tgrelid
    join pg_catalog.pg_namespace n on n.oid = c.relnamespace
    join pg_catalog.pg_proc p on p.oid = t.tgfoid
    where n.nspname = 'public'
      and c.relname = 'household_members'
      and t.tgname = 'household_members_preserve_active_owner'
      and not t.tgisinternal
      and t.tgenabled = 'O'
      and p.proname = 'prevent_last_active_owner_removal'
  ) then
    raise exception 'last-active-owner guard trigger is missing or disabled';
  end if;

  if exists (
    select 1
    from pg_catalog.pg_proc p
    join pg_catalog.pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'private'
      and p.proname = 'prevent_last_active_owner_removal'
      and (
        not p.prosecdef
        or coalesce(array_to_string(p.proconfig, ','), '') not like '%search_path=%'
        or coalesce(array_to_string(p.proconfig, ','), '') not like '%row_security=off%'
      )
  ) or not exists (
    select 1
    from pg_catalog.pg_proc p
    join pg_catalog.pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'private'
      and p.proname = 'prevent_last_active_owner_removal'
  ) then
    raise exception 'last-active-owner guard function is not hardened';
  end if;

  if position(
    'insert into public.audit_events' in lower(pg_get_functiondef(
      to_regprocedure('public.void_transaction(uuid,uuid,text)')
    ))
  ) = 0 then
    raise exception 'void_transaction must append an audit event';
  end if;

  if position(
    '(''other'', ''expense''' in lower(pg_get_functiondef(
      to_regprocedure('public.setup_household(text,text,jsonb,jsonb)')
    ))
  ) = 0 then
    raise exception 'setup_household must seed the Other expense fallback category';
  end if;

  if exists (
    select 1
    from unnest(array[
      'profiles', 'households', 'household_members', 'accounts', 'categories',
      'transactions', 'transaction_splits', 'settlements', 'transfer_links',
      'merchant_rules', 'audit_events'
    ]) as required(table_name)
    where not has_table_privilege(
      'authenticated', format('public.%I', required.table_name), 'SELECT'
    )
  ) then
    raise exception 'authenticated role is missing required SELECT grants';
  end if;

  if exists (
    select 1
    from unnest(array[
      'profiles', 'households', 'household_members', 'accounts', 'categories',
      'transactions', 'transaction_splits', 'settlements', 'transfer_links',
      'merchant_rules', 'audit_events'
    ]) as exposed(table_name)
    where has_table_privilege('anon', format('public.%I', exposed.table_name), 'SELECT')
       or has_table_privilege('anon', format('public.%I', exposed.table_name), 'INSERT')
       or has_table_privilege('anon', format('public.%I', exposed.table_name), 'UPDATE')
       or has_table_privilege('anon', format('public.%I', exposed.table_name), 'DELETE')
  ) then
    raise exception 'anon role must not have ledger table privileges';
  end if;
end;
$$;

rollback;
