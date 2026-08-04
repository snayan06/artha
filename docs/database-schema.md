# Database structure

Artha uses PostgreSQL on Supabase in production. The local FastAPI demo uses a
smaller SQLite projection of the same ledger concepts. Every monetary value is
stored as an integer number of paise; floating-point money is never persisted.

```mermaid
erDiagram
    AUTH_USERS ||--|| PROFILES : owns
    PROFILES ||--o{ HOUSEHOLDS : creates
    HOUSEHOLDS ||--o{ HOUSEHOLD_MEMBERS : contains
    PROFILES o|--o{ HOUSEHOLD_MEMBERS : can_join
    HOUSEHOLDS ||--o{ ACCOUNTS : owns
    HOUSEHOLDS ||--o{ CATEGORIES : defines
    HOUSEHOLDS ||--o{ TRANSACTIONS : records
    ACCOUNTS ||--o{ TRANSACTIONS : posts_to
    CATEGORIES o|--o{ TRANSACTIONS : classifies
    HOUSEHOLD_MEMBERS ||--o{ TRANSACTIONS : paid_by
    TRANSACTIONS ||--o{ TRANSACTION_SPLITS : allocates
    HOUSEHOLD_MEMBERS ||--o{ TRANSACTION_SPLITS : owes_share
    HOUSEHOLDS ||--o{ SETTLEMENTS : records
    HOUSEHOLD_MEMBERS ||--o{ SETTLEMENTS : payer
    HOUSEHOLD_MEMBERS ||--o{ SETTLEMENTS : payee
    TRANSACTIONS ||--o| TRANSFER_LINKS : links_out
    TRANSACTIONS ||--o| TRANSFER_LINKS : links_in
    HOUSEHOLDS ||--o{ MERCHANT_RULES : learns
    CATEGORIES ||--o{ MERCHANT_RULES : assigns
    HOUSEHOLDS ||--o{ AUDIT_EVENTS : audits

    PROFILES {
        uuid id PK
        text display_name
        timestamptz created_at
    }
    HOUSEHOLDS {
        uuid id PK
        text name
        uuid created_by FK
    }
    HOUSEHOLD_MEMBERS {
        uuid id PK
        uuid household_id FK
        uuid profile_id FK "nullable participant"
        text display_name
        text member_type "user or participant"
        text role "owner or member"
        boolean is_active
    }
    ACCOUNTS {
        uuid id PK
        uuid household_id FK
        text name
        text account_type "bank cash wallet credit_card other"
        text currency
        bigint opening_balance_paise
        bigint credit_limit_paise
        smallint statement_day
        smallint payment_due_day
        boolean is_archived
    }
    CATEGORIES {
        uuid id PK
        uuid household_id FK
        text name
        text category_type
        text icon
    }
    TRANSACTIONS {
        uuid id PK
        uuid household_id FK
        uuid account_id FK
        uuid category_id FK
        uuid paid_by_member_id FK
        text direction
        bigint amount_paise
        timestamptz occurred_at
        text merchant
        text note
        text status
        text idempotency_key
        text request_hash
        jsonb metadata
    }
    TRANSACTION_SPLITS {
        uuid id PK
        uuid household_id FK
        uuid transaction_id FK
        uuid member_id FK
        bigint amount_paise
    }
    SETTLEMENTS {
        uuid id PK
        uuid household_id FK
        uuid payer_member_id FK
        uuid payee_member_id FK
        uuid account_id FK
        uuid transaction_id FK
        bigint amount_paise
        timestamptz settled_at
    }
    TRANSFER_LINKS {
        uuid id PK
        uuid household_id FK
        uuid transfer_out_transaction_id FK
        uuid transfer_in_transaction_id FK
    }
    MERCHANT_RULES {
        uuid id PK
        uuid household_id FK
        text merchant_pattern
        text match_type
        uuid category_id FK
        uuid account_id FK
        integer priority
    }
    AUDIT_EVENTS {
        bigint id PK
        uuid household_id FK
        uuid actor_profile_id FK
        text entity_type
        uuid entity_id
        text action
        jsonb payload
        timestamptz occurred_at
    }
```

## How a shared expense is stored

For an expense of Rs 1,200 paid from a bank account and shared by three family
members, Artha writes one `transactions` row and up to three
`transaction_splits` rows. The split rows must add up exactly to the transaction
amount. A database function performs the transaction, splits, and audit event in
one atomic operation and uses an idempotency key so retries cannot duplicate the
expense.

## Balance rules

- Bank, cash, and wallet opening balances are positive assets.
- Credit-card outstanding debt is a negative opening balance.
- Transfers are two linked transaction rows, never income or spending.
- Settlements reduce member balances without becoming an expense.
- Posted transactions are voided instead of being destructively deleted.

## Auto-tagging data

`merchant_rules` is the household's learned tagging layer. A corrected merchant
can be mapped to a category and optional account. These deterministic rules run
before the LLM. When no rule matches, the assistant may suggest one of the
existing category IDs with a confidence score; it cannot invent or write a
category silently.

## Security boundary

Supabase Auth owns login identities. Row Level Security limits every query to a
household the signed-in profile belongs to. Composite foreign keys prevent a row
from referring to an account, category, member, or transaction in another
household. The LLM receives compact read-only summaries from approved server
tools; it never receives database credentials and never executes SQL.
