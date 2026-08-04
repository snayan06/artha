from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, model_validator

from .assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantFinancialContext,
    AssistantStatus,
    ContextCategory,
    ContextMemberBalance,
    ContextMonth,
    ContextTransaction,
    LocalFinancialAssistant,
    TagSuggestionRequest,
    TagSuggestionResponse,
)
from .auth import AuthDependency
from .schemas import AccountCreate, MemberCreate, ParseRequest
from .supabase_rest import SupabaseRestClient, rest_client_for_request

router = APIRouter()


async def production_client(
    request: Request,
    auth: AuthDependency,
) -> SupabaseRestClient:
    return rest_client_for_request(request, auth)


ClientDependency = Annotated[SupabaseRestClient, Depends(production_client)]


class ProductionOnboardingRequest(BaseModel):
    display_name: str = Field(default="You", min_length=1, max_length=100)
    household_name: str = Field(default="My household", min_length=1, max_length=100)
    accounts: list[AccountCreate] = Field(min_length=1, max_length=20)
    members: list[MemberCreate] = Field(default_factory=list, max_length=20)


class ProductionSplit(BaseModel):
    member_id: UUID
    amount_paise: int = Field(gt=0)


class ProductionDraft(BaseModel):
    kind: Literal["expense", "income"]
    amount_paise: int = Field(gt=0)
    description: str = Field(min_length=1, max_length=240)
    category: str = Field(min_length=1, max_length=80)
    paid_by_member_id: UUID | None = None
    personal_share_paise: int = Field(ge=0)
    splits: list[ProductionSplit] = Field(default_factory=list, max_length=20)
    source_account_id: UUID
    occurred_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def split_total_matches(self) -> ProductionDraft:
        if self.personal_share_paise + sum(item.amount_paise for item in self.splits) != (
            self.amount_paise
        ):
            raise ValueError("personal and member splits must add up to the total")
        if self.kind == "income" and self.splits:
            raise ValueError("income cannot contain household splits")
        return self


async def current_household(client: SupabaseRestClient, *, required: bool = True) -> str | None:
    household_id = await client.rpc("get_current_household")
    if household_id is None and required:
        raise HTTPException(status.HTTP_409_CONFLICT, "complete household onboarding first")
    return str(household_id) if household_id is not None else None


async def member_rows(client: SupabaseRestClient, household_id: str) -> list[dict[str, Any]]:
    rows = await client.request(
        "GET",
        "household_members",
        params={
            "household_id": f"eq.{household_id}",
            "is_active": "eq.true",
            "select": "id,profile_id,display_name,member_type,role,is_active,created_at",
            "order": "created_at.asc,id.asc",
        },
    )
    return list(rows or [])


async def owner_member(
    client: SupabaseRestClient,
    household_id: str,
    user_id: str,
) -> dict[str, Any]:
    rows = await member_rows(client, household_id)
    owner = next(
        (
            row
            for row in rows
            if row.get("profile_id") == user_id and row.get("role") == "owner"
        ),
        None,
    )
    if owner is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "active household owner was not found")
    return owner


async def account_rows(client: SupabaseRestClient, household_id: str) -> list[dict[str, Any]]:
    accounts = await client.request(
        "GET",
        "accounts",
        params={
            "household_id": f"eq.{household_id}",
            "is_archived": "eq.false",
            "select": (
                "id,name,account_type,currency,opening_balance_paise,"
                "credit_limit_paise,statement_day,payment_due_day,is_archived,created_at"
            ),
            "order": "created_at.asc,id.asc",
        },
    )
    balances = await client.rpc("get_account_balances", {"p_household_id": household_id})
    balance_by_id = {str(row["account_id"]): int(row["balance_paise"]) for row in balances}
    return [
        {
            **row,
            "kind": row["account_type"],
            "current_balance_paise": balance_by_id.get(
                str(row["id"]), int(row["opening_balance_paise"])
            ),
        }
        for row in accounts
    ]


def public_member(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["display_name"],
        "is_archived": not bool(row["is_active"]),
        "created_at": row["created_at"],
    }


@router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "v1-production"}


@router.get("/api/v1/accounts", tags=["accounts"])
async def list_accounts(client: ClientDependency) -> list[dict[str, Any]]:
    household_id = await current_household(client)
    assert household_id is not None
    return await account_rows(client, household_id)


@router.get("/api/v1/members", tags=["members"])
async def list_members(client: ClientDependency) -> list[dict[str, Any]]:
    household_id = await current_household(client)
    assert household_id is not None
    return [public_member(row) for row in await member_rows(client, household_id)]


@router.post(
    "/api/v1/onboarding/setup",
    status_code=status.HTTP_201_CREATED,
    tags=["onboarding"],
)
async def setup_onboarding(
    payload: ProductionOnboardingRequest,
    client: ClientDependency,
) -> dict[str, Any]:
    await client.rpc(
        "setup_household",
        {
            "p_display_name": payload.display_name.strip(),
            "p_household_name": payload.household_name.strip(),
            "p_members": [{"name": member.name} for member in payload.members],
            "p_accounts": [
                {
                    "name": account.name,
                    "account_type": account.kind.value,
                    "currency": "INR",
                    "opening_balance_paise": account.opening_balance_paise,
                    "credit_limit_paise": account.credit_limit_paise,
                    "statement_day": account.statement_day,
                    "payment_due_day": account.payment_due_day,
                }
                for account in payload.accounts
            ],
        },
    )
    household_id = await current_household(client)
    assert household_id is not None
    return {
        "accounts": await account_rows(client, household_id),
        "members": [public_member(row) for row in await member_rows(client, household_id)],
    }


async def categories_by_id(
    client: SupabaseRestClient, household_id: str
) -> dict[str, dict[str, Any]]:
    rows = await client.request(
        "GET",
        "categories",
        params={
            "household_id": f"eq.{household_id}",
            "is_archived": "eq.false",
            "select": "id,name,category_type",
        },
    )
    return {str(row["id"]): row for row in rows}


async def transaction_rows(
    client: SupabaseRestClient,
    household_id: str,
    *,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    rows = await client.request(
        "GET",
        "transactions",
        params={
            "household_id": f"eq.{household_id}",
            "status": "eq.posted",
            "select": (
                "id,account_id,category_id,paid_by_member_id,direction,amount_paise,"
                "currency,occurred_at,merchant,note,status,created_at,"
                "transaction_splits(member_id,amount_paise)"
            ),
            "order": "occurred_at.desc,id.desc",
            "limit": str(limit),
            "offset": str(offset),
        },
    )
    return list(rows or [])


def transaction_view(
    row: dict[str, Any],
    owner_id: str,
    categories: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    all_splits = list(row.get("transaction_splits") or [])
    personal_share = next(
        (
            int(split["amount_paise"])
            for split in all_splits
            if str(split["member_id"]) == owner_id
        ),
        0,
    )
    shared_splits = [split for split in all_splits if str(split["member_id"]) != owner_id]
    category = categories.get(str(row.get("category_id")), {}).get("name")
    direction = str(row["direction"])
    return {
        "id": row["id"],
        "kind": "income" if direction == "income" else "expense",
        "amount_paise": int(row["amount_paise"]),
        "personal_share_paise": personal_share,
        "description": row.get("merchant") or ("Income" if direction == "income" else "Expense"),
        "category": category,
        "paid_by_member_id": row.get("paid_by_member_id"),
        "source_account_id": row["account_id"],
        "destination_account_id": None,
        "settlement_member_id": None,
        "settlement_direction": None,
        "occurred_at": row["occurred_at"],
        "notes": row.get("note"),
        "splits": shared_splits,
        "is_deleted": False,
        "created_at": row["created_at"],
        "updated_at": row["created_at"],
        "account_delta_paise": int(row["amount_paise"]) * (1 if direction == "income" else -1),
        "member_balance_deltas": [
            {"member_id": split["member_id"], "amount_paise": int(split["amount_paise"])}
            for split in shared_splits
        ],
    }


@router.get("/api/v1/transactions", tags=["transactions"])
async def list_transactions(
    client: ClientDependency,
    auth: AuthDependency,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[dict[str, Any]]:
    household_id = await current_household(client)
    assert household_id is not None
    owner = await owner_member(client, household_id, auth.user_id)
    categories = await categories_by_id(client, household_id)
    return [
        transaction_view(row, str(owner["id"]), categories)
        for row in await transaction_rows(client, household_id, limit=limit, offset=offset)
        if row["direction"] in {"expense", "income"}
    ]


@router.post(
    "/api/v1/transactions/confirm",
    status_code=status.HTTP_201_CREATED,
    tags=["transactions"],
)
async def confirm_transaction(
    payload: ProductionDraft,
    client: ClientDependency,
    auth: AuthDependency,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)],
) -> dict[str, Any]:
    household_id = await current_household(client)
    assert household_id is not None
    owner = await owner_member(client, household_id, auth.user_id)
    owner_id = str(owner["id"])
    category_rows = await client.request(
        "GET",
        "categories",
        params={
            "household_id": f"eq.{household_id}",
            "name": f"ilike.{payload.category}",
            "is_archived": "eq.false",
            "select": "id,name,category_type",
            "limit": "1",
        },
    )
    if not category_rows:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "category is not available")
    paid_by_member_id = str(payload.paid_by_member_id or owner_id)
    splits = [split.model_dump(mode="json") for split in payload.splits]
    if payload.personal_share_paise:
        splits.append({"member_id": owner_id, "amount_paise": payload.personal_share_paise})
    result = await client.rpc(
        "confirm_transaction",
        {
            "p_household_id": household_id,
            "p_account_id": str(payload.source_account_id),
            "p_category_id": str(category_rows[0]["id"]),
            "p_paid_by_member_id": paid_by_member_id,
            "p_direction": payload.kind,
            "p_amount_paise": payload.amount_paise,
            "p_currency": "INR",
            "p_occurred_at": (payload.occurred_at or datetime.now(UTC)).isoformat(),
            "p_splits": splits,
            "p_idempotency_key": idempotency_key,
            "p_merchant": payload.description,
            "p_note": payload.notes,
            "p_metadata": {"source": "hisab-api"},
        },
    )
    result["transaction_splits"] = splits
    result["created_at"] = result.get("created_at") or datetime.now(UTC).isoformat()
    return transaction_view(result, owner_id, {str(category_rows[0]["id"]): category_rows[0]})


def member_balances(
    rows: list[dict[str, Any]], members: list[dict[str, Any]], owner_id: str
) -> list[dict[str, Any]]:
    balances: dict[str, int] = defaultdict(int)
    for row in rows:
        if row["direction"] != "expense":
            continue
        paid_by = str(row.get("paid_by_member_id"))
        splits = list(row.get("transaction_splits") or [])
        if paid_by == owner_id:
            for split in splits:
                member_id = str(split["member_id"])
                if member_id != owner_id:
                    balances[member_id] += int(split["amount_paise"])
        else:
            owner_share = next(
                (
                    int(split["amount_paise"])
                    for split in splits
                    if str(split["member_id"]) == owner_id
                ),
                0,
            )
            balances[paid_by] -= owner_share
    return [
        {
            "member_id": member["id"],
            "member_name": member["display_name"],
            "balance_paise": balances[str(member["id"])],
            "status": "owes you" if balances[str(member["id"])] > 0 else "you owe",
        }
        for member in members
        if str(member["id"]) != owner_id and balances[str(member["id"])] != 0
    ]


@router.get("/api/v1/dashboard", tags=["dashboard"])
async def dashboard(client: ClientDependency, auth: AuthDependency) -> dict[str, Any]:
    household_id = await current_household(client)
    assert household_id is not None
    owner = await owner_member(client, household_id, auth.user_id)
    owner_id = str(owner["id"])
    members = await member_rows(client, household_id)
    accounts = await account_rows(client, household_id)
    categories = await categories_by_id(client, household_id)
    rows = await transaction_rows(client, household_id, limit=1000)
    views = [
        transaction_view(row, owner_id, categories)
        for row in rows
        if row["direction"] in {"expense", "income"}
    ]
    now = datetime.now(UTC)
    month_key = now.strftime("%Y-%m")
    current = [view for view in views if str(view["occurred_at"]).startswith(month_key)]
    category_totals: dict[str, int] = defaultdict(int)
    for view in current:
        if view["kind"] == "expense":
            category_totals[str(view["category"] or "Uncategorized")] += int(
                view["personal_share_paise"]
            )
    monthly: list[dict[str, Any]] = []
    for months_back in range(5, -1, -1):
        absolute = now.year * 12 + now.month - 1 - months_back
        year, month_index = divmod(absolute, 12)
        key = f"{year:04d}-{month_index + 1:02d}"
        matching = [view for view in views if str(view["occurred_at"]).startswith(key)]
        monthly.append(
            {
                "month": datetime(year, month_index + 1, 1, tzinfo=UTC).strftime("%b"),
                "income_paise": sum(
                    int(view["personal_share_paise"])
                    for view in matching
                    if view["kind"] == "income"
                ),
                "spend_paise": sum(
                    int(view["personal_share_paise"])
                    for view in matching
                    if view["kind"] == "expense"
                ),
            }
        )
    return {
        "total_balance_paise": sum(int(account["current_balance_paise"]) for account in accounts),
        "spend_paise": sum(category_totals.values()),
        "income_paise": sum(
            int(view["personal_share_paise"])
            for view in current
            if view["kind"] == "income"
        ),
        "net_cashflow_paise": sum(
            int(view["amount_paise"]) * (1 if view["kind"] == "income" else -1)
            for view in views
        ),
        "member_balances": member_balances(rows, members, owner_id),
        "accounts": accounts,
        "spend_by_category": [
            {"category": name, "amount_paise": amount}
            for name, amount in sorted(
                category_totals.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "monthly": monthly,
        "recent_transactions": views[:10],
    }


@router.post("/api/v1/drafts/parse", tags=["transactions"])
async def parse_draft(_payload: ParseRequest, _auth: AuthDependency) -> None:
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        "server-side production parsing is not enabled; use the validated client parser",
    )


def safe_label(value: Any, fallback: str = "Uncategorized") -> str:
    printable = "".join(character for character in str(value or "") if character.isprintable())
    return printable.strip()[:40] or fallback


@router.get("/api/v1/assistant/status", response_model=AssistantStatus, tags=["assistant"])
async def assistant_status(_auth: AuthDependency) -> AssistantStatus:
    return await LocalFinancialAssistant().status()


@router.post(
    "/api/v1/assistant/chat",
    response_model=AssistantChatResponse,
    tags=["assistant"],
)
async def assistant_chat(
    payload: AssistantChatRequest,
    client: ClientDependency,
    auth: AuthDependency,
) -> AssistantChatResponse:
    summary = await dashboard(client, auth)
    context = AssistantFinancialContext(
        total_balance_paise=int(summary["total_balance_paise"]),
        current_month_spend_paise=int(summary["spend_paise"]),
        current_month_income_paise=int(summary["income_paise"]),
        member_balances=[
            ContextMemberBalance(
                member_name=safe_label(row["member_name"], "Household member"),
                balance_paise=int(row["balance_paise"]),
            )
            for row in list(summary["member_balances"])[:20]
        ],
        top_categories=[
            ContextCategory(
                category=safe_label(row["category"]),
                amount_paise=int(row["amount_paise"]),
            )
            for row in list(summary["spend_by_category"])[:5]
        ],
        monthly=[
            ContextMonth(
                month=safe_label(row["month"])[:12],
                income_paise=int(row["income_paise"]),
                spend_paise=int(row["spend_paise"]),
            )
            for row in list(summary["monthly"])[-6:]
        ],
        recent_transactions=[
            ContextTransaction(
                occurred_on=str(row["occurred_at"])[:10],
                kind="income" if row["kind"] == "income" else "expense",
                personal_share_paise=int(row["personal_share_paise"]),
                category=safe_label(row.get("category")),
            )
            for row in list(summary["recent_transactions"])[:8]
        ],
    )
    return await LocalFinancialAssistant().chat(payload.message, context)


@router.post(
    "/api/v1/assistant/tag-suggestion",
    response_model=TagSuggestionResponse,
    tags=["assistant"],
)
async def assistant_tag_suggestion(
    payload: TagSuggestionRequest,
    _auth: AuthDependency,
) -> TagSuggestionResponse:
    return await LocalFinancialAssistant().suggest_tag(payload)
