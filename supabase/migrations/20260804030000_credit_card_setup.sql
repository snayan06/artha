-- Credit-card onboarding metadata. Outstanding card debt is represented as a
-- negative opening balance so account aggregation produces a net position.

alter table public.accounts
  add column statement_day smallint,
  add column payment_due_day smallint,
  add constraint accounts_statement_day_ck
    check (statement_day is null or statement_day between 1 and 31),
  add constraint accounts_payment_due_day_ck
    check (payment_due_day is null or payment_due_day between 1 and 31),
  add constraint accounts_credit_metadata_ck
    check (
      account_type = 'credit_card'
      or (
        credit_limit_paise is null
        and statement_day is null
        and payment_due_day is null
      )
    ),
  add constraint accounts_credit_card_opening_balance_ck
    check (account_type <> 'credit_card' or opening_balance_paise <= 0);

comment on column public.accounts.opening_balance_paise is
  'Opening asset balance in paise; credit-card outstanding debt is negative.';
comment on column public.accounts.statement_day is
  'Optional day of month on which a credit-card statement is generated.';
comment on column public.accounts.payment_due_day is
  'Optional day of month on which a credit-card payment is due.';
