"""Verify that production PostgREST can resolve Artha's required RPCs.

Required environment variables are intentionally supplied at runtime:
ARTHA_SUPABASE_URL and ARTHA_SUPABASE_ANON_KEY. Values are never printed.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request


REQUIRED_RPCS = {
    "get_account_balances": {
        "p_household_id": "00000000-0000-0000-0000-000000000000"
    },
    "list_ledger_activity": {
        "p_household_id": "00000000-0000-0000-0000-000000000000",
        "p_limit": 1,
        "p_offset": 0,
    },
    "export_household_bundle": {},
    "restore_household_bundle": {
        "p_bundle": {},
        "p_idempotency_key": "catalog-probe",
    },
}


def probe_rpc(base_url: str, anon_key: str, name: str, payload: dict[str, object]) -> None:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/rest/v1/rpc/{name}",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status = response.status
            body = response.read()
    except urllib.error.HTTPError as error:
        status = error.code
        body = error.read()

    try:
        error_code = str(json.loads(body or b"{}").get("code", ""))
    except (json.JSONDecodeError, AttributeError):
        error_code = ""

    if status == 404 or error_code == "PGRST202":
        raise RuntimeError(f"required RPC is missing from PostgREST schema cache: {name}")
    if status not in {200, 400, 401, 403}:
        raise RuntimeError(f"unexpected status while probing {name}: {status}")


def main() -> None:
    base_url = os.environ["ARTHA_SUPABASE_URL"]
    anon_key = os.environ["ARTHA_SUPABASE_ANON_KEY"]
    expected_ref = os.environ["ARTHA_SUPABASE_PROJECT_REF"]
    parsed_url = urllib.parse.urlsplit(base_url)
    expected_host = f"{expected_ref}.supabase.co"
    if parsed_url.scheme != "https" or parsed_url.hostname != expected_host:
        raise RuntimeError(
            "ARTHA_SUPABASE_URL does not match ARTHA_SUPABASE_PROJECT_REF; "
            "refusing to probe a different project"
        )
    for name, payload in REQUIRED_RPCS.items():
        probe_rpc(base_url, anon_key, name, payload)
    print(f"live-rpc-catalog-ok required={len(REQUIRED_RPCS)}")


if __name__ == "__main__":
    main()
