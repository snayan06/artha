-- Exact, owner-scoped logical activity lookup for evidence drill-down.
create function public.get_ledger_activity(
  p_household_id uuid,
  p_activity_id uuid
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
set row_security = off
as $$
declare
  v_result jsonb;
begin
  if auth.uid() is null or not private.is_household_owner(p_household_id) then
    raise exception 'not authorized for household' using errcode = '42501';
  end if;

  with owner_member as materialized (
    select hm.id
    from public.household_members hm
    where hm.household_id = p_household_id
      and hm.profile_id = auth.uid()
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
      coalesce(
        t.merchant,
        case when t.direction = 'income' then 'Income' else 'Expense' end
      ) as description,
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
      and t.id = p_activity_id
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
      and tl.id = p_activity_id
  ),
  settlement_activity as (
    select
      movement.id,
      'settlement'::text as kind,
      s.amount_paise,
      0::bigint as personal_share_paise,
      case
        when s.payer_member_id = owner.id
          then 'Repayment to ' || other_member.display_name
        else 'Repayment from ' || other_member.display_name
      end as description,
      'Shared repayment'::text as category,
      s.payer_member_id as paid_by_member_id,
      s.account_id as source_account_id,
      null::uuid as destination_account_id,
      other_member.id as settlement_member_id,
      s.account_direction as settlement_direction,
      s.settled_at as occurred_at,
      s.note as notes,
      '[]'::jsonb as splits,
      false as is_deleted,
      movement.created_at,
      movement.created_at as updated_at,
      s.amount_paise
        * case when s.account_direction = 'settlement_in' then 1 else -1 end
        as account_delta_paise,
      jsonb_build_array(jsonb_build_object(
        'member_id', other_member.id,
        'amount_paise', s.amount_paise
          * case when s.payer_member_id = owner.id then 1 else -1 end
      )) as member_balance_deltas
    from public.settlements s
    join owner_member owner on owner.id in (s.payer_member_id, s.payee_member_id)
    join public.household_members other_member
      on other_member.household_id = s.household_id
      and other_member.id = case
        when s.payer_member_id = owner.id then s.payee_member_id
        else s.payer_member_id
      end
    join public.transactions movement
      on movement.household_id = s.household_id
      and movement.id = s.transaction_id
      and movement.status = 'posted'
    where s.household_id = p_household_id
      and movement.id = p_activity_id
  ),
  adjustment_activity as (
    select
      t.id,
      'adjustment'::text as kind,
      t.amount_paise,
      0::bigint as personal_share_paise,
      'Balance correction'::text as description,
      'Balance correction'::text as category,
      null::uuid as paid_by_member_id,
      t.account_id as source_account_id,
      null::uuid as destination_account_id,
      null::uuid as settlement_member_id,
      t.direction as settlement_direction,
      t.occurred_at,
      t.note as notes,
      '[]'::jsonb as splits,
      false as is_deleted,
      t.created_at,
      t.created_at as updated_at,
      t.amount_paise * case when t.direction = 'adjustment_in' then 1 else -1 end
        as account_delta_paise,
      '[]'::jsonb as member_balance_deltas
    from public.transactions t
    where t.household_id = p_household_id
      and t.id = p_activity_id
      and t.status = 'posted'
      and t.direction in ('adjustment_in', 'adjustment_out')
  ),
  logical_activity as (
    select * from ordinary_activity
    union all
    select * from transfer_activity
    union all
    select * from settlement_activity
    union all
    select * from adjustment_activity
  )
  select to_jsonb(activity)
  into v_result
  from logical_activity activity
  limit 1;

  return v_result;
end;
$$;

revoke all on function public.get_ledger_activity(uuid, uuid)
  from public, anon, service_role;
grant execute on function public.get_ledger_activity(uuid, uuid)
  to authenticated;

notify pgrst, 'reload schema';
