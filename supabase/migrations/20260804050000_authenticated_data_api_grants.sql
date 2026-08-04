-- Explicit Data API privileges for projects created with automatic table
-- exposure disabled. RLS remains the row-level authorization boundary.

grant usage on schema public to authenticated;

grant select on table
  public.profiles,
  public.households,
  public.household_members,
  public.accounts,
  public.categories,
  public.transactions,
  public.transaction_splits,
  public.settlements,
  public.transfer_links,
  public.merchant_rules,
  public.audit_events
to authenticated;

-- These mutable reference tables already have household-scoped RLS policies.
-- Ledger facts remain RPC-only and receive no direct mutation grants.
grant update on table public.profiles, public.households to authenticated;
grant insert, update, delete on table public.merchant_rules to authenticated;

revoke all on table
  public.profiles,
  public.households,
  public.household_members,
  public.accounts,
  public.categories,
  public.transactions,
  public.transaction_splits,
  public.settlements,
  public.transfer_links,
  public.merchant_rules,
  public.audit_events
from anon;

alter default privileges in schema public revoke all on tables from anon;
alter default privileges in schema public revoke all on sequences from anon;

