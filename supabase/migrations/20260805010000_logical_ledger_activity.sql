-- Page user-facing ledger activity after paired transfer rows have been joined.
-- Applying limit/offset to raw transactions can split a transfer pair and make
-- the logical transfer disappear from history.

create index transfer_links_household_created_idx
  on public.transfer_links (household_id, created_at desc, id desc);

create or replace function public.list_ledger_activity(
  p_household_id uuid,
  p_limit integer default 100,
  p_offset integer default 0
)
returns table (
  id uuid,
  kind text,
  amount_paise bigint,
  personal_share_paise bigint,
  description text,
  category text,
  paid_by_member_id uuid,
  source_account_id uuid,
  destination_account_id uuid,
  settlement_member_id uuid,
  settlement_direction text,
  occurred_at timestamptz,
  notes text,
  splits jsonb,
  is_deleted boolean,
  created_at timestamptz,
  updated_at timestamptz,
  account_delta_paise bigint,
  member_balance_deltas jsonb
)
language plpgsql
stable
security definer
set search_path = ''
set row_security = off
as $$
begin
  if auth.uid() is null or not private.is_household_owner(p_household_id) then
    raise exception 'not authorized for household' using errcode = '42501';
  end if;
  if p_limit is null or p_limit not between 1 and 1000 then
    raise exception 'limit must be between 1 and 1000' using errcode = '22023';
  end if;
  if p_offset is null or p_offset not between 0 and 100000 then
    raise exception 'offset must be between 0 and 100000' using errcode = '22023';
  end if;

  return query
  with owner_member as materialized (
    select hm.id
    from public.household_members hm
    where hm.household_id = p_household_id
      and hm.profile_id = auth.uid()
      and hm.member_type = 'user'
      and hm.role = 'owner'
      and hm.is_active
    limit 1
  ),
  ordinary_activity as (
    select
      t.id,
      t.direction as kind,
      t.amount_paise,
      coalesce(owner_split.amount_paise, 0::bigint) as personal_share_paise,
      coalesce(t.merchant, case when t.direction = 'income' then 'Income' else 'Expense' end)
        as description,
      c.name as category,
      t.paid_by_member_id,
      t.account_id as source_account_id,
      null::uuid as destination_account_id,
      null::uuid as settlement_member_id,
      null::text as settlement_direction,
      t.occurred_at,
      t.note as notes,
      coalesce(shared.splits, '[]'::jsonb) as splits,
      false as is_deleted,
      t.created_at,
      t.created_at as updated_at,
      t.amount_paise * case when t.direction = 'income' then 1 else -1 end
        as account_delta_paise,
      coalesce(shared.splits, '[]'::jsonb) as member_balance_deltas
    from public.transactions t
    cross join owner_member owner
    left join public.categories c
      on c.household_id = t.household_id and c.id = t.category_id
    left join lateral (
      select ts.amount_paise
      from public.transaction_splits ts
      where ts.household_id = t.household_id
        and ts.transaction_id = t.id
        and ts.member_id = owner.id
      limit 1
    ) owner_split on true
    left join lateral (
      select jsonb_agg(
        jsonb_build_object(
          'member_id', ts.member_id,
          'amount_paise', ts.amount_paise
        ) order by ts.member_id
      ) as splits
      from public.transaction_splits ts
      where ts.household_id = t.household_id
        and ts.transaction_id = t.id
        and ts.member_id <> owner.id
    ) shared on true
    where t.household_id = p_household_id
      and t.status = 'posted'
      and t.direction in ('expense', 'income')
  ),
  transfer_activity as (
    select
      tl.id,
      'transfer'::text as kind,
      transfer_out.amount_paise,
      transfer_out.amount_paise as personal_share_paise,
      coalesce(transfer_out.note, 'Account transfer') as description,
      'Transfer'::text as category,
      null::uuid as paid_by_member_id,
      transfer_out.account_id as source_account_id,
      transfer_in.account_id as destination_account_id,
      null::uuid as settlement_member_id,
      null::text as settlement_direction,
      transfer_out.occurred_at,
      transfer_out.note as notes,
      '[]'::jsonb as splits,
      false as is_deleted,
      tl.created_at,
      tl.created_at as updated_at,
      0::bigint as account_delta_paise,
      '[]'::jsonb as member_balance_deltas
    from public.transfer_links tl
    join public.transactions transfer_out
      on transfer_out.household_id = tl.household_id
      and transfer_out.id = tl.transfer_out_transaction_id
      and transfer_out.direction = 'transfer_out'
      and transfer_out.status = 'posted'
    join public.transactions transfer_in
      on transfer_in.household_id = tl.household_id
      and transfer_in.id = tl.transfer_in_transaction_id
      and transfer_in.direction = 'transfer_in'
      and transfer_in.status = 'posted'
    where tl.household_id = p_household_id
  ),
  logical_activity as (
    select * from ordinary_activity
    union all
    select * from transfer_activity
  )
  select
    activity.id,
    activity.kind,
    activity.amount_paise,
    activity.personal_share_paise,
    activity.description,
    activity.category,
    activity.paid_by_member_id,
    activity.source_account_id,
    activity.destination_account_id,
    activity.settlement_member_id,
    activity.settlement_direction,
    activity.occurred_at,
    activity.notes,
    activity.splits,
    activity.is_deleted,
    activity.created_at,
    activity.updated_at,
    activity.account_delta_paise,
    activity.member_balance_deltas
  from logical_activity activity
  order by activity.occurred_at desc, activity.created_at desc, activity.id desc
  limit p_limit
  offset p_offset;
end;
$$;

revoke all on function public.list_ledger_activity(uuid, integer, integer)
  from public, anon, service_role;
grant execute on function public.list_ledger_activity(uuid, integer, integer)
  to authenticated;
