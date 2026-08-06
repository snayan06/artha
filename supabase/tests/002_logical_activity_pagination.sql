-- Focused contract for pair-safe ledger pagination. A full Supabase test run
-- executes this after all migrations have been applied.
begin;

do $$
declare
  v_function regprocedure := to_regprocedure(
    'public.list_ledger_activity(uuid,integer,integer)'
  );
  v_definition text;
begin
  if v_function is null then
    raise exception 'list_ledger_activity RPC is missing';
  end if;

  select lower(pg_get_functiondef(v_function)) into v_definition;

  if position('from public.transfer_links' in v_definition) = 0
     or position('transfer_out.direction = ''transfer_out''' in v_definition) = 0
     or position('transfer_in.direction = ''transfer_in''' in v_definition) = 0 then
    raise exception 'logical activity must join both rows of every transfer';
  end if;

  if position('union all' in v_definition) = 0
     or position('order by activity.occurred_at' in v_definition)
       < position('union all' in v_definition)
     or position('limit p_limit' in v_definition)
       < position('order by activity.occurred_at' in v_definition)
     or position('offset p_offset' in v_definition)
       < position('limit p_limit' in v_definition) then
    raise exception 'limit and offset must apply after the logical activity union';
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
    raise exception 'logical activity RPC is not hardened and stable';
  end if;

  if not has_function_privilege('authenticated', v_function, 'EXECUTE')
     or has_function_privilege('anon', v_function, 'EXECUTE')
     or has_function_privilege('service_role', v_function, 'EXECUTE') then
    raise exception 'logical activity RPC privileges are unsafe';
  end if;
end;
$$;

rollback;
