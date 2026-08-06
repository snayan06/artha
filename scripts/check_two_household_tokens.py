"""Read-only hosted Supabase two-household isolation check.

Credentials are accepted only through process environment variables and are
never written or printed:

ARTHA_SUPABASE_URL
ARTHA_SUPABASE_ANON_KEY
ARTHA_USER_A_TOKEN
ARTHA_USER_B_TOKEN

The two users must already be authenticated and onboarded into different
households. Run from an environment whose shell history and process environment
are appropriately protected.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Identity:
    label: str
    token: str
    user_id: str


class CheckFailure(RuntimeError):
    """A sanitized acceptance failure that never includes credentials."""


def required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise CheckFailure(f"missing required environment variable: {name}")
    return value


def jwt_subject(token: str, label: str) -> str:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("token must contain three segments")
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
        subject = str(claims["sub"])
        uuid.UUID(subject)
        return subject
    except (
        KeyError,
        ValueError,
        TypeError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as error:
        raise CheckFailure(f"{label} token does not contain a valid UUID subject") from error


def validate_base_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise CheckFailure("ARTHA_SUPABASE_URL must be a bare HTTPS project origin")
    return value.rstrip("/")


class SupabaseRest:
    def __init__(self, base_url: str, anon_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.anon_key = anon_key

    def request(
        self,
        identity: Identity | None,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        payload: dict[str, object] | None = None,
        allowed_statuses: set[int] | None = None,
    ) -> tuple[int, Any]:
        url = f"{self.base_url}/rest/v1/{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        authorization = identity.token if identity else self.anon_key
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={
                "apikey": self.anon_key,
                "Authorization": f"Bearer {authorization}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                status = response.status
                content = response.read()
        except urllib.error.HTTPError as error:
            status = error.code
            content = error.read()
        except urllib.error.URLError as error:
            raise CheckFailure("hosted Supabase request could not connect") from error

        expected = allowed_statuses or {200}
        if status not in expected:
            target = identity.label if identity else "anonymous"
            raise CheckFailure(f"unexpected HTTP {status} for {target} {method} {path}")
        if not content:
            return status, None
        try:
            return status, json.loads(content)
        except json.JSONDecodeError as error:
            raise CheckFailure(f"non-JSON response for {method} {path}") from error


def list_rows(
    rest: SupabaseRest,
    identity: Identity,
    table: str,
    select: str,
    **filters: str,
) -> list[dict[str, object]]:
    _, payload = rest.request(
        identity,
        "GET",
        table,
        params={"select": select, **filters},
    )
    if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
        raise CheckFailure(f"unexpected row shape for {identity.label} {table}")
    return payload


def current_household(rest: SupabaseRest, identity: Identity) -> str:
    _, payload = rest.request(identity, "POST", "rpc/get_current_household", payload={})
    try:
        household_id = str(payload)
        uuid.UUID(household_id)
        return household_id
    except ValueError as error:
        raise CheckFailure(f"{identity.label} does not have one valid current household") from error


def assert_user_scope(
    rest: SupabaseRest,
    identity: Identity,
    own_household: str,
    other_household: str,
) -> int:
    profiles = list_rows(rest, identity, "profiles", "id")
    if {str(row.get("id")) for row in profiles} != {identity.user_id}:
        raise CheckFailure(f"{identity.label} profile scope is not self-only")

    households = list_rows(rest, identity, "households", "id")
    if {str(row.get("id")) for row in households} != {own_household}:
        raise CheckFailure(f"{identity.label} household scope is not exactly one own household")

    household_tables = (
        "household_members",
        "accounts",
        "categories",
        "transactions",
        "transaction_splits",
        "settlements",
        "transfer_links",
        "merchant_rules",
        "audit_events",
    )
    checked_rows = 0
    for table in household_tables:
        rows = list_rows(rest, identity, table, "household_id")
        if any(str(row.get("household_id")) != own_household for row in rows):
            raise CheckFailure(f"{identity.label} can see another household in {table}")
        checked_rows += len(rows)
        cross_rows = list_rows(
            rest,
            identity,
            table,
            "household_id",
            household_id=f"eq.{other_household}",
        )
        if cross_rows:
            raise CheckFailure(f"{identity.label} can filter-read the other household in {table}")

    cross_household = list_rows(
        rest,
        identity,
        "households",
        "id",
        id=f"eq.{other_household}",
    )
    if cross_household:
        raise CheckFailure(f"{identity.label} can directly read the other household")

    status, _ = rest.request(
        identity,
        "POST",
        "rpc/get_account_balances",
        payload={"p_household_id": other_household},
        allowed_statuses={401, 403},
    )
    if status not in {401, 403}:
        raise CheckFailure(f"{identity.label} cross-household balance RPC was not denied")
    return checked_rows


def main() -> int:
    try:
        base_url = validate_base_url(required_environment("ARTHA_SUPABASE_URL"))
        anon_key = required_environment("ARTHA_SUPABASE_ANON_KEY")
        token_a = required_environment("ARTHA_USER_A_TOKEN")
        token_b = required_environment("ARTHA_USER_B_TOKEN")
        identity_a = Identity("user A", token_a, jwt_subject(token_a, "user A"))
        identity_b = Identity("user B", token_b, jwt_subject(token_b, "user B"))
        if identity_a.user_id == identity_b.user_id:
            raise CheckFailure("the two tokens belong to the same user")

        rest = SupabaseRest(base_url, anon_key)
        household_a = current_household(rest, identity_a)
        household_b = current_household(rest, identity_b)
        if household_a == household_b:
            raise CheckFailure("the two users belong to the same household")

        checked_rows = assert_user_scope(rest, identity_a, household_a, household_b)
        checked_rows += assert_user_scope(rest, identity_b, household_b, household_a)

        status, anonymous = rest.request(
            None,
            "GET",
            "accounts",
            params={"select": "id"},
            allowed_statuses={200, 401, 403},
        )
        if status == 200 and anonymous != []:
            raise CheckFailure("anonymous account read returned rows")

        print(
            "hosted-two-household-ok users=2 households=2 "
            f"scoped_rows={checked_rows} cross_rows=0 cross_rpc_denials=2 anon_rows=0"
        )
        return 0
    except CheckFailure as error:
        print(f"hosted-two-household-failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
