-- P1 ledger hardening: payer attribution, replay-safe writes, atomic transfers and
-- settlements, and immutable opening balances for ordinary authenticated users.

create extension if not exists pgcrypto with schema extensions;

alter table public.transactions
  add column paid_by_member_id uuid,
  add column request_hash text,
  add constraint transactions_household_paid_by_fk
    foreign key (household_id, paid_by_member_id)
    references public.household_members (household_id, id) on delete restrict,
  add constraint transactions_request_hash_ck
    check (request_hash is null or request_hash ~ '^[0-9a-f]{64}$');

-- Preserve any pre-migration data by assigning the creating user's member row.
update public.transactions t
set paid_by_member_id = hm.id
from public.household_members hm
where t.direction in ('expense', 'income')
  and t.paid_by_member_id is null
  and hm.household_id = t.household_id
  and hm.profile_id = t.created_by;

-- NOT VALID avoids breaking an installation with irreparable legacy rows while
-- still enforcing payer attribution for every new expense/income row.
alter table public.transactions
  add constraint transactions_cashflow_payer_ck
  check (
    direction not in ('expense', 'income')
    or (paid_by_member_id is not null and request_hash is not null and idempotency_key is not null)
  ) not valid;

create index transactions_paid_by_idx
  on public.transactions (household_id, paid_by_member_id, occurred_at desc)
  where paid_by_member_id is not null and status = 'posted';

alter table public.transfer_links
  add column created_by uuid references public.profiles (id) on delete restrict,
  add column idempotency_key text,
  add column request_hash text,
  add constraint transfer_links_idempotency_key_ck
    check (idempotency_key is null or char_length(idempotency_key) between 8 and 160),
  add constraint transfer_links_request_hash_ck
    check (request_hash is null or request_hash ~ '^[0-9a-f]{64}$');

create unique index transfer_links_idempotency_idx
  on public.transfer_links (household_id, created_by, idempotency_key)
  where idempotency_key is not null;

alter table public.settlements
  add column account_id uuid,
  add column account_direction text,
  add column transaction_id uuid,
  add column idempotency_key text,
  add column request_hash text,
  add constraint settlements_account_direction_ck
    check (account_direction is null or account_direction in ('settlement_out', 'settlement_in')),
  add constraint settlements_idempotency_key_ck
    check (idempotency_key is null or char_length(idempotency_key) between 8 and 160),
  add constraint settlements_request_hash_ck
    check (request_hash is null or request_hash ~ '^[0-9a-f]{64}$'),
  add constraint settlements_household_account_fk
    foreign key (household_id, account_id)
    references public.accounts (household_id, id) on delete restrict,
  add constraint settlements_household_transaction_fk
    foreign key (household_id, transaction_id)
    references public.transactions (household_id, id) on delete restrict,
  add constraint settlements_transaction_unique unique (transaction_id);

create unique index settlements_idempotency_idx
  on public.settlements (household_id, created_by, idempotency_key)
  where idempotency_key is not null;

-- New settlement writes must use create_settlement(). Legacy rows remain valid,
-- but clients can no longer bypass the linked transaction and audit event.
drop policy if exists settlements_insert_member on public.settlements;

create or replace function private.protect_account_opening_balance()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if old.opening_balance_paise is distinct from new.opening_balance_paise
     and current_user = 'authenticated' then
    raise exception 'opening balance is immutable after account creation'
      using errcode = '42501';
  end if;
  return new;
end;
$$;

create trigger accounts_protect_opening_balance
before update on public.accounts
for each row execute function private.protect_account_opening_balance();

-- Replace the permissive V1 signature. The new payer and required idempotency
-- key are part of the canonical payload, so a retry is safe and a key reuse with
-- different data is rejected.
drop function if exists public.confirm_transaction(
  uuid, uuid, uuid, text, bigint, text, timestamptz, jsonb, text, text, text, jsonb
);

create or replace function public.confirm_transaction(
  p_household_id uuid,
  p_account_id uuid,
  p_category_id uuid,
  p_paid_by_member_id uuid,
  p_direction text,
  p_amount_paise bigint,
  p_currency text,
  p_occurred_at timestamptz,
  p_splits jsonb,
  p_idempotency_key text,
  p_merchant text default null,
  p_note text default null,
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
  v_canonical_splits jsonb;
  v_request_hash text;
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
  if p_idempotency_key is null
     or char_length(trim(p_idempotency_key)) not between 8 and 160 then
    raise exception 'idempotency_key is required (8-160 characters)'
      using errcode = '22023';
  end if;
  if p_metadata is null or jsonb_typeof(p_metadata) <> 'object' then
    raise exception 'metadata must be a JSON object' using errcode = '22023';
  end if;
  if not exists (
    select 1 from public.household_members hm
    where hm.household_id = p_household_id
      and hm.id = p_paid_by_member_id
      and hm.is_active
  ) then
    raise exception 'paid_by_member_id must be an active household member'
      using errcode = '23514';
  end if;
  if not exists (
    select 1 from public.accounts a
    where a.household_id = p_household_id
      and a.id = p_account_id
      and a.currency = p_currency
      and not a.is_archived
  ) then
    raise exception 'account must be active, in the household, and use the transaction currency'
      using errcode = '23514';
  end if;
  if not exists (
    select 1 from public.categories c
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

  select
    count(*),
    coalesce(sum((s.value ->> 'amount_paise')::bigint), 0),
    jsonb_agg(
      jsonb_build_object(
        'member_id', (s.value ->> 'member_id')::uuid,
        'amount_paise', (s.value ->> 'amount_paise')::bigint
      ) order by (s.value ->> 'member_id')::uuid
    )
  into v_split_count, v_split_total, v_canonical_splits
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

  v_request_hash := encode(
    extensions.digest(
      convert_to(jsonb_build_object(
        'household_id', p_household_id,
        'account_id', p_account_id,
        'category_id', p_category_id,
        'paid_by_member_id', p_paid_by_member_id,
        'direction', p_direction,
        'amount_paise', p_amount_paise,
        'currency', p_currency,
        'occurred_at', p_occurred_at,
        'splits', v_canonical_splits,
        'merchant', nullif(trim(p_merchant), ''),
        'note', p_note,
        'metadata', p_metadata
      )::text, 'UTF8'),
      'sha256'
    ),
    'hex'
  );

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    p_household_id::text || ':' || auth.uid()::text || ':confirm:' || trim(p_idempotency_key),
    0
  ));

  select * into v_transaction
  from public.transactions t
  where t.household_id = p_household_id
    and t.created_by = auth.uid()
    and t.idempotency_key = trim(p_idempotency_key);

  if found then
    if v_transaction.request_hash = v_request_hash then
      return v_transaction;
    end if;
    raise exception 'idempotency key was already used with a different request'
      using errcode = '23505';
  end if;

  insert into public.transactions (
    household_id, account_id, category_id, paid_by_member_id, direction,
    amount_paise, currency, occurred_at, merchant, note, idempotency_key,
    request_hash, metadata, created_by
  ) values (
    p_household_id, p_account_id, p_category_id, p_paid_by_member_id, p_direction,
    p_amount_paise, p_currency, p_occurred_at, nullif(trim(p_merchant), ''),
    p_note, trim(p_idempotency_key), v_request_hash, p_metadata, auth.uid()
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
  from jsonb_array_elements(v_canonical_splits) s(value);

  insert into public.audit_events (
    household_id, actor_profile_id, entity_type, entity_id, action, payload
  ) values (
    p_household_id,
    auth.uid(),
    'transaction',
    v_transaction.id,
    'confirmed',
    jsonb_build_object(
      'amount_paise', p_amount_paise,
      'direction', p_direction,
      'paid_by_member_id', p_paid_by_member_id,
      'request_hash', v_request_hash
    )
  );

  return v_transaction;
end;
$$;

revoke all on function public.confirm_transaction(
  uuid, uuid, uuid, uuid, text, bigint, text, timestamptz, jsonb, text, text, text, jsonb
) from public, anon;
grant execute on function public.confirm_transaction(
  uuid, uuid, uuid, uuid, text, bigint, text, timestamptz, jsonb, text, text, text, jsonb
) to authenticated;

create or replace function public.create_transfer(
  p_household_id uuid,
  p_from_account_id uuid,
  p_to_account_id uuid,
  p_amount_paise bigint,
  p_currency text,
  p_occurred_at timestamptz,
  p_idempotency_key text,
  p_note text default null
)
returns table (
  transfer_link_id uuid,
  transfer_out_transaction_id uuid,
  transfer_in_transaction_id uuid
)
language plpgsql
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_link public.transfer_links;
  v_out public.transactions;
  v_in public.transactions;
  v_request_hash text;
begin
  if auth.uid() is null or not private.is_household_member(p_household_id) then
    raise exception 'not authorized for household' using errcode = '42501';
  end if;
  if p_from_account_id = p_to_account_id then
    raise exception 'transfer accounts must differ' using errcode = '22023';
  end if;
  if p_amount_paise is null or p_amount_paise <= 0 then
    raise exception 'amount_paise must be positive' using errcode = '22023';
  end if;
  if p_idempotency_key is null
     or char_length(trim(p_idempotency_key)) not between 8 and 160 then
    raise exception 'idempotency_key is required (8-160 characters)'
      using errcode = '22023';
  end if;
  if (
    select count(*)
    from public.accounts a
    where a.household_id = p_household_id
      and a.id in (p_from_account_id, p_to_account_id)
      and a.currency = p_currency
      and not a.is_archived
  ) <> 2 then
    raise exception 'both accounts must be active household accounts with the transfer currency'
      using errcode = '23514';
  end if;

  v_request_hash := encode(extensions.digest(convert_to(jsonb_build_object(
    'household_id', p_household_id,
    'from_account_id', p_from_account_id,
    'to_account_id', p_to_account_id,
    'amount_paise', p_amount_paise,
    'currency', p_currency,
    'occurred_at', p_occurred_at,
    'note', p_note
  )::text, 'UTF8'), 'sha256'), 'hex');

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    p_household_id::text || ':' || auth.uid()::text || ':transfer:' || trim(p_idempotency_key),
    0
  ));

  select * into v_link
  from public.transfer_links tl
  where tl.household_id = p_household_id
    and tl.created_by = auth.uid()
    and tl.idempotency_key = trim(p_idempotency_key);

  if found then
    if v_link.request_hash is distinct from v_request_hash then
      raise exception 'idempotency key was already used with a different request'
        using errcode = '23505';
    end if;
    return query select v_link.id, v_link.transfer_out_transaction_id,
      v_link.transfer_in_transaction_id;
    return;
  end if;

  insert into public.transactions (
    household_id, account_id, direction, amount_paise, currency, occurred_at,
    note, metadata, created_by
  ) values (
    p_household_id, p_from_account_id, 'transfer_out', p_amount_paise,
    p_currency, p_occurred_at, p_note, '{}'::jsonb, auth.uid()
  ) returning * into v_out;

  insert into public.transactions (
    household_id, account_id, direction, amount_paise, currency, occurred_at,
    note, metadata, created_by
  ) values (
    p_household_id, p_to_account_id, 'transfer_in', p_amount_paise,
    p_currency, p_occurred_at, p_note, '{}'::jsonb, auth.uid()
  ) returning * into v_in;

  insert into public.transfer_links (
    household_id, transfer_out_transaction_id, transfer_in_transaction_id,
    created_by, idempotency_key, request_hash
  ) values (
    p_household_id, v_out.id, v_in.id, auth.uid(), trim(p_idempotency_key),
    v_request_hash
  ) returning * into v_link;

  insert into public.audit_events (
    household_id, actor_profile_id, entity_type, entity_id, action, payload
  ) values (
    p_household_id,
    auth.uid(),
    'transfer_link',
    v_link.id,
    'created',
    jsonb_build_object(
      'transfer_out_transaction_id', v_out.id,
      'transfer_in_transaction_id', v_in.id,
      'amount_paise', p_amount_paise,
      'request_hash', v_request_hash
    )
  );

  return query select v_link.id, v_out.id, v_in.id;
end;
$$;

revoke all on function public.create_transfer(
  uuid, uuid, uuid, bigint, text, timestamptz, text, text
) from public, anon;
grant execute on function public.create_transfer(
  uuid, uuid, uuid, bigint, text, timestamptz, text, text
) to authenticated;

create or replace function public.create_settlement(
  p_household_id uuid,
  p_payer_member_id uuid,
  p_payee_member_id uuid,
  p_account_id uuid,
  p_account_direction text,
  p_amount_paise bigint,
  p_currency text,
  p_settled_at timestamptz,
  p_idempotency_key text,
  p_note text default null
)
returns public.settlements
language plpgsql
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_settlement public.settlements;
  v_transaction public.transactions;
  v_request_hash text;
begin
  if auth.uid() is null or not private.is_household_member(p_household_id) then
    raise exception 'not authorized for household' using errcode = '42501';
  end if;
  if p_payer_member_id = p_payee_member_id then
    raise exception 'settlement members must differ' using errcode = '22023';
  end if;
  if p_account_direction not in ('settlement_out', 'settlement_in') then
    raise exception 'account_direction must be settlement_out or settlement_in'
      using errcode = '22023';
  end if;
  if p_amount_paise is null or p_amount_paise <= 0 then
    raise exception 'amount_paise must be positive' using errcode = '22023';
  end if;
  if p_idempotency_key is null
     or char_length(trim(p_idempotency_key)) not between 8 and 160 then
    raise exception 'idempotency_key is required (8-160 characters)'
      using errcode = '22023';
  end if;
  if (
    select count(*)
    from public.household_members hm
    where hm.household_id = p_household_id
      and hm.id in (p_payer_member_id, p_payee_member_id)
      and hm.is_active
  ) <> 2 then
    raise exception 'payer and payee must be active household members'
      using errcode = '23514';
  end if;
  if not exists (
    select 1 from public.accounts a
    where a.household_id = p_household_id
      and a.id = p_account_id
      and a.currency = p_currency
      and not a.is_archived
  ) then
    raise exception 'settlement account must be active and use the settlement currency'
      using errcode = '23514';
  end if;

  v_request_hash := encode(extensions.digest(convert_to(jsonb_build_object(
    'household_id', p_household_id,
    'payer_member_id', p_payer_member_id,
    'payee_member_id', p_payee_member_id,
    'account_id', p_account_id,
    'account_direction', p_account_direction,
    'amount_paise', p_amount_paise,
    'currency', p_currency,
    'settled_at', p_settled_at,
    'note', p_note
  )::text, 'UTF8'), 'sha256'), 'hex');

  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    p_household_id::text || ':' || auth.uid()::text || ':settlement:' || trim(p_idempotency_key),
    0
  ));

  select * into v_settlement
  from public.settlements s
  where s.household_id = p_household_id
    and s.created_by = auth.uid()
    and s.idempotency_key = trim(p_idempotency_key);

  if found then
    if v_settlement.request_hash = v_request_hash then
      return v_settlement;
    end if;
    raise exception 'idempotency key was already used with a different request'
      using errcode = '23505';
  end if;

  insert into public.transactions (
    household_id, account_id, direction, amount_paise, currency, occurred_at,
    note, metadata, created_by
  ) values (
    p_household_id, p_account_id, p_account_direction, p_amount_paise,
    p_currency, p_settled_at, p_note, '{}'::jsonb, auth.uid()
  ) returning * into v_transaction;

  insert into public.settlements (
    household_id, payer_member_id, payee_member_id, account_id,
    account_direction, transaction_id, amount_paise, currency, settled_at,
    note, created_by, idempotency_key, request_hash
  ) values (
    p_household_id, p_payer_member_id, p_payee_member_id, p_account_id,
    p_account_direction, v_transaction.id, p_amount_paise, p_currency,
    p_settled_at, p_note, auth.uid(), trim(p_idempotency_key), v_request_hash
  ) returning * into v_settlement;

  insert into public.audit_events (
    household_id, actor_profile_id, entity_type, entity_id, action, payload
  ) values (
    p_household_id,
    auth.uid(),
    'settlement',
    v_settlement.id,
    'created',
    jsonb_build_object(
      'transaction_id', v_transaction.id,
      'payer_member_id', p_payer_member_id,
      'payee_member_id', p_payee_member_id,
      'account_direction', p_account_direction,
      'amount_paise', p_amount_paise,
      'request_hash', v_request_hash
    )
  );

  return v_settlement;
end;
$$;

revoke all on function public.create_settlement(
  uuid, uuid, uuid, uuid, text, bigint, text, timestamptz, text, text
) from public, anon;
grant execute on function public.create_settlement(
  uuid, uuid, uuid, uuid, text, bigint, text, timestamptz, text, text
) to authenticated;
