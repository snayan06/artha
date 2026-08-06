-- Versioned household recovery primitives. Encryption and passphrase handling
-- happen in the browser; these RPCs only export or atomically restore the
-- authenticated owner's validated plaintext bundle.

create or replace function public.export_household_bundle()
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_user_id uuid := auth.uid();
  v_household_id uuid;
  v_household_name text;
  v_display_name text;
begin
  if v_user_id is null then
    raise exception 'authentication required' using errcode = '42501';
  end if;

  select hm.household_id, h.name, p.display_name
  into strict v_household_id, v_household_name, v_display_name
  from public.household_members hm
  join public.households h on h.id = hm.household_id
  join public.profiles p on p.id = v_user_id
  where hm.profile_id = v_user_id
    and hm.member_type = 'user'
    and hm.role = 'owner'
    and hm.is_active;

  return jsonb_build_object(
    'format', 'artha-recovery',
    'schema_version', 1,
    'exported_at', now(),
    'household', jsonb_build_object('name', v_household_name),
    'profile', jsonb_build_object('display_name', v_display_name),
    'members', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'source_id', hm.id,
        'display_name', hm.display_name,
        'member_type', hm.member_type,
        'role', hm.role,
        'is_active', hm.is_active
      ) order by hm.created_at, hm.id), '[]'::jsonb)
      from public.household_members hm
      where hm.household_id = v_household_id
    ),
    'accounts', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'source_id', a.id,
        'name', a.name,
        'account_type', a.account_type,
        'currency', a.currency,
        'opening_balance_paise', a.opening_balance_paise,
        'credit_limit_paise', a.credit_limit_paise,
        'statement_day', a.statement_day,
        'payment_due_day', a.payment_due_day,
        'is_archived', a.is_archived,
        'created_at', a.created_at
      ) order by a.created_at, a.id), '[]'::jsonb)
      from public.accounts a
      where a.household_id = v_household_id
    ),
    'categories', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'source_id', c.id,
        'name', c.name,
        'category_type', c.category_type,
        'icon', c.icon,
        'is_archived', c.is_archived,
        'created_at', c.created_at
      ) order by c.created_at, c.id), '[]'::jsonb)
      from public.categories c
      where c.household_id = v_household_id
    ),
    'transactions', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'source_id', t.id,
        'account_source_id', t.account_id,
        'category_source_id', t.category_id,
        'paid_by_member_source_id', t.paid_by_member_id,
        'direction', t.direction,
        'amount_paise', t.amount_paise,
        'currency', t.currency,
        'occurred_at', t.occurred_at,
        'merchant', t.merchant,
        'note', t.note,
        'status', t.status,
        'metadata', t.metadata,
        'created_at', t.created_at,
        'voided_at', t.voided_at
      ) order by t.created_at, t.id), '[]'::jsonb)
      from public.transactions t
      where t.household_id = v_household_id
    ),
    'splits', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'transaction_source_id', ts.transaction_id,
        'member_source_id', ts.member_id,
        'amount_paise', ts.amount_paise
      ) order by ts.transaction_id, ts.member_id), '[]'::jsonb)
      from public.transaction_splits ts
      where ts.household_id = v_household_id
    ),
    'transfers', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'source_id', tl.id,
        'out_transaction_source_id', tl.transfer_out_transaction_id,
        'in_transaction_source_id', tl.transfer_in_transaction_id,
        'created_at', tl.created_at
      ) order by tl.created_at, tl.id), '[]'::jsonb)
      from public.transfer_links tl
      where tl.household_id = v_household_id
    ),
    'settlements', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'source_id', s.id,
        'payer_member_source_id', s.payer_member_id,
        'payee_member_source_id', s.payee_member_id,
        'account_source_id', s.account_id,
        'transaction_source_id', s.transaction_id,
        'account_direction', s.account_direction,
        'amount_paise', s.amount_paise,
        'currency', s.currency,
        'settled_at', s.settled_at,
        'note', s.note,
        'created_at', s.created_at
      ) order by s.created_at, s.id), '[]'::jsonb)
      from public.settlements s
      where s.household_id = v_household_id
    ),
    'merchant_rules', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'source_id', mr.id,
        'match_type', mr.match_type,
        'merchant_pattern', mr.merchant_pattern,
        'category_source_id', mr.category_id,
        'account_source_id', mr.account_id,
        'priority', mr.priority,
        'is_active', mr.is_active,
        'created_at', mr.created_at
      ) order by mr.created_at, mr.id), '[]'::jsonb)
      from public.merchant_rules mr
      where mr.household_id = v_household_id
    ),
    'audit_events', (
      select coalesce(jsonb_agg(jsonb_build_object(
        'source_id', ae.id,
        'entity_type', ae.entity_type,
        'entity_source_id', ae.entity_id,
        'action', ae.action,
        'payload', ae.payload,
        'occurred_at', ae.occurred_at
      ) order by ae.id), '[]'::jsonb)
      from public.audit_events ae
      where ae.household_id = v_household_id
    )
  );
exception
  when no_data_found then
    raise exception 'active owner household not found' using errcode = 'P0002';
  when too_many_rows then
    raise exception 'exactly one active owner household is required' using errcode = '21000';
end;
$$;

revoke all on function public.export_household_bundle()
  from public, anon, service_role;
grant execute on function public.export_household_bundle() to authenticated;

create or replace function public.restore_household_bundle(
  p_bundle jsonb,
  p_idempotency_key text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_user_id uuid := auth.uid();
  v_household_id uuid;
  v_owner_member_id uuid;
  v_source_owner_id text;
  v_item jsonb;
  v_new_id uuid;
  v_member_map jsonb := '{}'::jsonb;
  v_account_map jsonb := '{}'::jsonb;
  v_category_map jsonb := '{}'::jsonb;
  v_transaction_map jsonb := '{}'::jsonb;
  v_transfer_map jsonb := '{}'::jsonb;
  v_settlement_map jsonb := '{}'::jsonb;
  v_rule_map jsonb := '{}'::jsonb;
  v_entity_id uuid;
  v_previous jsonb;
  v_summary jsonb;
begin
  if v_user_id is null then
    raise exception 'authentication required' using errcode = '42501';
  end if;
  if p_idempotency_key is null
     or char_length(trim(p_idempotency_key)) not between 8 and 128 then
    raise exception 'idempotency key must contain 8-128 characters'
      using errcode = '22023';
  end if;

  select jsonb_build_object(
    'household_id', ae.household_id,
    'restored', true,
    'idempotent_replay', true,
    'summary', ae.payload -> 'summary'
  )
  into v_previous
  from public.audit_events ae
  where ae.actor_profile_id = v_user_id
    and ae.action = 'recovery_restored'
    and ae.payload ->> 'idempotency_key' = trim(p_idempotency_key)
  order by ae.id desc
  limit 1;
  if v_previous is not null then
    return v_previous;
  end if;

  if p_bundle is null
     or jsonb_typeof(p_bundle) <> 'object'
     or p_bundle ->> 'format' <> 'artha-recovery'
     or p_bundle ->> 'schema_version' <> '1' then
    raise exception 'unsupported recovery bundle' using errcode = '22023';
  end if;
  if exists (
    select 1 from public.household_members hm
    where hm.profile_id = v_user_id and hm.is_active
  ) then
    raise exception 'restore requires an account with no active household'
      using errcode = '23505';
  end if;
  if jsonb_typeof(p_bundle -> 'members') <> 'array'
     or jsonb_array_length(p_bundle -> 'members') not between 1 and 100
     or jsonb_typeof(p_bundle -> 'accounts') <> 'array'
     or jsonb_array_length(p_bundle -> 'accounts') not between 1 and 100
     or jsonb_typeof(p_bundle -> 'categories') <> 'array'
     or jsonb_array_length(p_bundle -> 'categories') not between 1 and 200
     or jsonb_typeof(p_bundle -> 'transactions') <> 'array'
     or jsonb_array_length(p_bundle -> 'transactions') > 50000
     or jsonb_typeof(p_bundle -> 'splits') <> 'array'
     or jsonb_array_length(p_bundle -> 'splits') > 100000
     or jsonb_typeof(p_bundle -> 'transfers') <> 'array'
     or jsonb_array_length(p_bundle -> 'transfers') > 50000
     or jsonb_typeof(p_bundle -> 'settlements') <> 'array'
     or jsonb_array_length(p_bundle -> 'settlements') > 50000
     or jsonb_typeof(p_bundle -> 'merchant_rules') <> 'array'
     or jsonb_array_length(p_bundle -> 'merchant_rules') > 5000
     or jsonb_typeof(p_bundle -> 'audit_events') <> 'array'
     or jsonb_array_length(p_bundle -> 'audit_events') > 100000 then
    raise exception 'recovery bundle collection limits are invalid'
      using errcode = '22023';
  end if;

  select m.value ->> 'source_id'
  into strict v_source_owner_id
  from jsonb_array_elements(p_bundle -> 'members') m(value)
  where m.value ->> 'member_type' = 'user'
    and m.value ->> 'role' = 'owner';

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended('artha:restore:' || v_user_id::text, 0)
  );

  insert into public.profiles (id, display_name)
  values (v_user_id, trim(p_bundle #>> '{profile,display_name}'))
  on conflict (id) do update
    set display_name = excluded.display_name;

  insert into public.households (name, created_by)
  values (trim(p_bundle #>> '{household,name}'), v_user_id)
  returning id into v_household_id;

  select hm.id into strict v_owner_member_id
  from public.household_members hm
  where hm.household_id = v_household_id
    and hm.profile_id = v_user_id
    and hm.role = 'owner';
  update public.household_members
  set display_name = trim(p_bundle #>> '{profile,display_name}')
  where id = v_owner_member_id;
  v_member_map := jsonb_set(
    v_member_map,
    array[v_source_owner_id],
    to_jsonb(v_owner_member_id::text),
    true
  );

  for v_item in select value from jsonb_array_elements(p_bundle -> 'members')
  loop
    if v_item ->> 'source_id' = v_source_owner_id then
      continue;
    end if;
    if v_item ->> 'member_type' <> 'participant'
       or v_item ->> 'role' <> 'member' then
      raise exception 'only the owner and participant members can be restored'
        using errcode = '22023';
    end if;
    insert into public.household_members (
      household_id, display_name, member_type, role, is_active
    ) values (
      v_household_id,
      trim(v_item ->> 'display_name'),
      'participant',
      'member',
      (v_item ->> 'is_active')::boolean
    ) returning id into v_new_id;
    v_member_map := jsonb_set(
      v_member_map,
      array[v_item ->> 'source_id'],
      to_jsonb(v_new_id::text),
      true
    );
  end loop;

  for v_item in select value from jsonb_array_elements(p_bundle -> 'accounts')
  loop
    insert into public.accounts (
      household_id, name, account_type, currency, opening_balance_paise,
      credit_limit_paise, statement_day, payment_due_day, is_archived,
      created_at, updated_at
    ) values (
      v_household_id,
      trim(v_item ->> 'name'),
      v_item ->> 'account_type',
      v_item ->> 'currency',
      (v_item ->> 'opening_balance_paise')::bigint,
      (v_item ->> 'credit_limit_paise')::bigint,
      (v_item ->> 'statement_day')::smallint,
      (v_item ->> 'payment_due_day')::smallint,
      (v_item ->> 'is_archived')::boolean,
      (v_item ->> 'created_at')::timestamptz,
      (v_item ->> 'created_at')::timestamptz
    ) returning id into v_new_id;
    v_account_map := jsonb_set(
      v_account_map,
      array[v_item ->> 'source_id'],
      to_jsonb(v_new_id::text),
      true
    );
  end loop;

  for v_item in select value from jsonb_array_elements(p_bundle -> 'categories')
  loop
    insert into public.categories (
      household_id, name, category_type, icon, is_archived, created_at, updated_at
    ) values (
      v_household_id,
      trim(v_item ->> 'name'),
      v_item ->> 'category_type',
      v_item ->> 'icon',
      (v_item ->> 'is_archived')::boolean,
      (v_item ->> 'created_at')::timestamptz,
      (v_item ->> 'created_at')::timestamptz
    ) returning id into v_new_id;
    v_category_map := jsonb_set(
      v_category_map,
      array[v_item ->> 'source_id'],
      to_jsonb(v_new_id::text),
      true
    );
  end loop;

  for v_item in select value from jsonb_array_elements(p_bundle -> 'transactions')
  loop
    insert into public.transactions (
      household_id, account_id, category_id, paid_by_member_id, direction,
      amount_paise, currency, occurred_at, merchant, note, status,
      idempotency_key, request_hash, metadata, created_by, created_at, voided_at
    ) values (
      v_household_id,
      (v_account_map ->> (v_item ->> 'account_source_id'))::uuid,
      (v_category_map ->> (v_item ->> 'category_source_id'))::uuid,
      (v_member_map ->> (v_item ->> 'paid_by_member_source_id'))::uuid,
      v_item ->> 'direction',
      (v_item ->> 'amount_paise')::bigint,
      v_item ->> 'currency',
      (v_item ->> 'occurred_at')::timestamptz,
      v_item ->> 'merchant',
      v_item ->> 'note',
      v_item ->> 'status',
      'restore-' || (v_item ->> 'source_id'),
      encode(extensions.digest(
        convert_to(v_household_id::text || ':' || (v_item ->> 'source_id'), 'UTF8'),
        'sha256'
      ), 'hex'),
      coalesce(v_item -> 'metadata', '{}'::jsonb) || jsonb_build_object('restored', true),
      v_user_id,
      (v_item ->> 'created_at')::timestamptz,
      (v_item ->> 'voided_at')::timestamptz
    ) returning id into v_new_id;
    v_transaction_map := jsonb_set(
      v_transaction_map,
      array[v_item ->> 'source_id'],
      to_jsonb(v_new_id::text),
      true
    );
  end loop;

  for v_item in select value from jsonb_array_elements(p_bundle -> 'splits')
  loop
    insert into public.transaction_splits (
      household_id, transaction_id, member_id, amount_paise
    ) values (
      v_household_id,
      (v_transaction_map ->> (v_item ->> 'transaction_source_id'))::uuid,
      (v_member_map ->> (v_item ->> 'member_source_id'))::uuid,
      (v_item ->> 'amount_paise')::bigint
    );
  end loop;

  for v_item in select value from jsonb_array_elements(p_bundle -> 'transfers')
  loop
    insert into public.transfer_links (
      household_id, transfer_out_transaction_id, transfer_in_transaction_id,
      created_at, created_by, idempotency_key, request_hash
    ) values (
      v_household_id,
      (v_transaction_map ->> (v_item ->> 'out_transaction_source_id'))::uuid,
      (v_transaction_map ->> (v_item ->> 'in_transaction_source_id'))::uuid,
      (v_item ->> 'created_at')::timestamptz,
      v_user_id,
      'restore-' || (v_item ->> 'source_id'),
      encode(extensions.digest(
        convert_to(v_household_id::text || ':transfer:' || (v_item ->> 'source_id'), 'UTF8'),
        'sha256'
      ), 'hex')
    ) returning id into v_new_id;
    v_transfer_map := jsonb_set(
      v_transfer_map,
      array[v_item ->> 'source_id'],
      to_jsonb(v_new_id::text),
      true
    );
  end loop;

  for v_item in select value from jsonb_array_elements(p_bundle -> 'settlements')
  loop
    insert into public.settlements (
      household_id, payer_member_id, payee_member_id, account_id,
      account_direction, transaction_id, amount_paise, currency, settled_at,
      note, created_by, created_at, idempotency_key, request_hash
    ) values (
      v_household_id,
      (v_member_map ->> (v_item ->> 'payer_member_source_id'))::uuid,
      (v_member_map ->> (v_item ->> 'payee_member_source_id'))::uuid,
      (v_account_map ->> (v_item ->> 'account_source_id'))::uuid,
      v_item ->> 'account_direction',
      (v_transaction_map ->> (v_item ->> 'transaction_source_id'))::uuid,
      (v_item ->> 'amount_paise')::bigint,
      v_item ->> 'currency',
      (v_item ->> 'settled_at')::timestamptz,
      v_item ->> 'note',
      v_user_id,
      (v_item ->> 'created_at')::timestamptz,
      'restore-' || (v_item ->> 'source_id'),
      encode(extensions.digest(
        convert_to(v_household_id::text || ':settlement:' || (v_item ->> 'source_id'), 'UTF8'),
        'sha256'
      ), 'hex')
    ) returning id into v_new_id;
    v_settlement_map := jsonb_set(
      v_settlement_map,
      array[v_item ->> 'source_id'],
      to_jsonb(v_new_id::text),
      true
    );
  end loop;

  for v_item in select value from jsonb_array_elements(p_bundle -> 'merchant_rules')
  loop
    insert into public.merchant_rules (
      household_id, match_type, merchant_pattern, category_id, account_id,
      priority, is_active, created_by, created_at, updated_at
    ) values (
      v_household_id,
      v_item ->> 'match_type',
      trim(v_item ->> 'merchant_pattern'),
      (v_category_map ->> (v_item ->> 'category_source_id'))::uuid,
      (v_account_map ->> (v_item ->> 'account_source_id'))::uuid,
      (v_item ->> 'priority')::integer,
      (v_item ->> 'is_active')::boolean,
      v_user_id,
      (v_item ->> 'created_at')::timestamptz,
      (v_item ->> 'created_at')::timestamptz
    ) returning id into v_new_id;
    v_rule_map := jsonb_set(
      v_rule_map,
      array[v_item ->> 'source_id'],
      to_jsonb(v_new_id::text),
      true
    );
  end loop;

  for v_item in select value from jsonb_array_elements(p_bundle -> 'audit_events')
  loop
    v_entity_id := case v_item ->> 'entity_type'
      when 'household' then v_household_id
      when 'profile' then v_user_id
      when 'member' then (v_member_map ->> (v_item ->> 'entity_source_id'))::uuid
      when 'account' then (v_account_map ->> (v_item ->> 'entity_source_id'))::uuid
      when 'category' then (v_category_map ->> (v_item ->> 'entity_source_id'))::uuid
      when 'transaction' then (v_transaction_map ->> (v_item ->> 'entity_source_id'))::uuid
      when 'transfer' then (v_transfer_map ->> (v_item ->> 'entity_source_id'))::uuid
      when 'settlement' then (v_settlement_map ->> (v_item ->> 'entity_source_id'))::uuid
      when 'merchant_rule' then (v_rule_map ->> (v_item ->> 'entity_source_id'))::uuid
      else null
    end;
    insert into public.audit_events (
      household_id, actor_profile_id, entity_type, entity_id, action,
      payload, occurred_at
    ) values (
      v_household_id,
      v_user_id,
      v_item ->> 'entity_type',
      v_entity_id,
      v_item ->> 'action',
      coalesce(v_item -> 'payload', '{}'::jsonb)
        || jsonb_build_object('restored_from_event_id', v_item ->> 'source_id'),
      (v_item ->> 'occurred_at')::timestamptz
    );
  end loop;

  v_summary := jsonb_build_object(
    'members', jsonb_array_length(p_bundle -> 'members'),
    'accounts', jsonb_array_length(p_bundle -> 'accounts'),
    'categories', jsonb_array_length(p_bundle -> 'categories'),
    'transactions', jsonb_array_length(p_bundle -> 'transactions'),
    'splits', jsonb_array_length(p_bundle -> 'splits'),
    'transfers', jsonb_array_length(p_bundle -> 'transfers'),
    'settlements', jsonb_array_length(p_bundle -> 'settlements'),
    'merchant_rules', jsonb_array_length(p_bundle -> 'merchant_rules'),
    'audit_events', jsonb_array_length(p_bundle -> 'audit_events')
  );

  insert into public.audit_events (
    household_id, actor_profile_id, entity_type, entity_id, action, payload
  ) values (
    v_household_id,
    v_user_id,
    'household',
    v_household_id,
    'recovery_restored',
    jsonb_build_object(
      'idempotency_key', trim(p_idempotency_key),
      'summary', v_summary,
      'schema_version', 1
    )
  );

  return jsonb_build_object(
    'household_id', v_household_id,
    'restored', true,
    'idempotent_replay', false,
    'summary', v_summary
  );
exception
  when no_data_found then
    raise exception 'recovery bundle is missing its owner'
      using errcode = '22023';
  when too_many_rows then
    raise exception 'recovery bundle must contain exactly one owner'
      using errcode = '22023';
end;
$$;

revoke all on function public.restore_household_bundle(jsonb, text)
  from public, anon, service_role;
grant execute on function public.restore_household_bundle(jsonb, text)
  to authenticated;

select pg_notify('pgrst', 'reload schema');
