-- Every command that can move an account balance must serialize with archive.
begin;

do $$
declare
  v_definition text;
begin
  select pg_catalog.pg_get_functiondef(
    'public.confirm_transaction(uuid,uuid,uuid,uuid,text,bigint,text,timestamptz,jsonb,text,text,text,jsonb)'::regprocedure
  ) into v_definition;
  if position('artha:account-row:' in v_definition) = 0 then
    raise exception 'confirm_transaction does not use the shared account lock';
  end if;

  select pg_catalog.pg_get_functiondef(
    'public.create_transfer(uuid,uuid,uuid,bigint,text,timestamptz,text,text)'::regprocedure
  ) into v_definition;
  if position('least(p_from_account_id, p_to_account_id)' in v_definition) = 0
    or position('greatest(p_from_account_id, p_to_account_id)' in v_definition) = 0 then
    raise exception 'create_transfer does not lock both accounts in deterministic order';
  end if;

  select pg_catalog.pg_get_functiondef(
    'public.create_settlement(uuid,uuid,uuid,uuid,text,bigint,text,timestamptz,text,text)'::regprocedure
  ) into v_definition;
  if position('artha:account-row:' in v_definition) = 0 then
    raise exception 'create_settlement does not use the shared account lock';
  end if;

  select pg_catalog.pg_get_functiondef(
    'public.create_balance_adjustment(uuid,uuid,bigint,text,timestamptz,text)'::regprocedure
  ) into v_definition;
  if position('artha:account-row:' in v_definition) = 0 then
    raise exception 'create_balance_adjustment does not use the shared account lock';
  end if;

  select pg_catalog.pg_get_functiondef(
    'public.set_managed_account_archived(uuid,uuid,boolean,text)'::regprocedure
  ) into v_definition;
  if position('artha:account-row:' in v_definition) = 0 then
    raise exception 'set_managed_account_archived does not use the shared account lock';
  end if;

  select pg_catalog.pg_get_functiondef(
    'public.void_transaction(uuid,uuid,text)'::regprocedure
  ) into v_definition;
  if position('artha:account-row:' in v_definition) = 0
    or position('order by t.account_id' in v_definition) = 0 then
    raise exception 'void_transaction does not lock affected accounts in deterministic order';
  end if;
end;
$$;

rollback;
