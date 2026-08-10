"""Exercise the settlement/account lock order with two real database sessions."""

from __future__ import annotations

import os
import threading
import time
from typing import Any

import psycopg


DATABASE_URL = os.environ.get(
    "ARTHA_TEST_DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
)
OWNER_ID = "72000000-0000-4000-8000-000000000001"
HOUSEHOLD_ID = "72000000-1000-4000-8000-000000000001"
ACCOUNT_ID = "72000000-1100-4000-8000-000000000001"
CATEGORY_ID = "72000000-1200-4000-8000-000000000001"
MEMBER_ID = "72000000-1300-4000-8000-000000000001"


def authenticated(cursor: psycopg.Cursor[Any]) -> None:
    cursor.execute("set local role authenticated")
    cursor.execute(
        "select set_config('request.jwt.claim.sub', %s, true)",
        (OWNER_ID,),
    )
    cursor.execute(
        "select set_config('request.jwt.claim.role', 'authenticated', true)"
    )
    cursor.execute("set local statement_timeout = '5s'")


def setup_fixture() -> None:
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into auth.users (
                  id, aud, role, email, encrypted_password, email_confirmed_at,
                  raw_app_meta_data, raw_user_meta_data, created_at, updated_at
                ) values (
                  %s::uuid, 'authenticated', 'authenticated',
                  'daily-concurrency@example.test', '', now(),
                  '{"provider":"email","providers":["email"]}'::jsonb,
                  '{"display_name":"Concurrency Owner"}'::jsonb, now(), now()
                )
                """,
                (OWNER_ID,),
            )
            cursor.execute(
                "insert into public.households (id, name, created_by) values (%s, %s, %s)",
                (HOUSEHOLD_ID, "Concurrency Household", OWNER_ID),
            )
            cursor.execute(
                """
                insert into public.household_members (
                  id, household_id, display_name, member_type, role
                ) values (%s, %s, %s, 'participant', 'member')
                """,
                (MEMBER_ID, HOUSEHOLD_ID, "Concurrency Member"),
            )
            cursor.execute(
                """
                insert into public.accounts (
                  id, household_id, name, account_type, opening_balance_paise
                ) values (%s, %s, %s, 'bank', 100000)
                """,
                (ACCOUNT_ID, HOUSEHOLD_ID, "Concurrency Bank"),
            )
            cursor.execute(
                """
                insert into public.categories (
                  id, household_id, name, category_type
                ) values (%s, %s, %s, 'expense')
                """,
                (CATEGORY_ID, HOUSEHOLD_ID, "Concurrency Expense"),
            )

    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            authenticated(cursor)
            cursor.execute(
                """
                select public.confirm_transaction(
                  %s, %s, %s,
                  (select id from public.household_members
                   where household_id = %s and profile_id = %s),
                  'expense', 5000, 'INR', now(),
                  jsonb_build_array(jsonb_build_object(
                    'member_id', %s::uuid, 'amount_paise', 5000
                  )),
                  'concurrency-shared-0001', 'Shared fixture', null, '{}'::jsonb
                )
                """,
                (
                    HOUSEHOLD_ID,
                    ACCOUNT_ID,
                    CATEGORY_ID,
                    HOUSEHOLD_ID,
                    OWNER_ID,
                    MEMBER_ID,
                ),
            )


def cleanup_fixture() -> None:
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "alter table public.household_members disable trigger "
                "household_members_preserve_active_owner"
            )
            try:
                for table in (
                    "private.member_settlement_requests",
                    "private.transaction_correction_requests",
                    "private.transaction_void_requests",
                    "public.audit_events",
                    "public.settlements",
                    "public.transaction_splits",
                    "public.transfer_links",
                    "public.transactions",
                    "public.categories",
                    "public.accounts",
                    "public.household_members",
                ):
                    cursor.execute(
                        f"delete from {table} where household_id = %s",  # noqa: S608
                        (HOUSEHOLD_ID,),
                    )
                cursor.execute(
                    "delete from public.households where id = %s", (HOUSEHOLD_ID,)
                )
                cursor.execute("delete from auth.users where id = %s", (OWNER_ID,))
            finally:
                cursor.execute(
                    "alter table public.household_members enable trigger "
                    "household_members_preserve_active_owner"
                )


def main() -> None:
    setup_fixture()
    writer_has_account = threading.Event()
    settlement_started = threading.Event()
    failures: list[BaseException] = []

    def writer() -> None:
        try:
            with psycopg.connect(DATABASE_URL) as connection:
                with connection.cursor() as cursor:
                    authenticated(cursor)
                    cursor.execute(
                        "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                        (f"artha:account-row:{ACCOUNT_ID}",),
                    )
                    writer_has_account.set()
                    if not settlement_started.wait(timeout=2):
                        raise RuntimeError("settlement session did not start")
                    time.sleep(0.25)
                    cursor.execute(
                        """
                        select public.confirm_transaction(
                          %s, %s, %s,
                          (select id from public.household_members
                           where household_id = %s and profile_id = %s),
                          'expense', 100, 'INR', now(),
                          jsonb_build_array(jsonb_build_object(
                            'member_id', %s::uuid, 'amount_paise', 100
                          )),
                          'concurrency-writer-0001', 'Concurrent write', null, '{}'::jsonb
                        )
                        """,
                        (
                            HOUSEHOLD_ID,
                            ACCOUNT_ID,
                            CATEGORY_ID,
                            HOUSEHOLD_ID,
                            OWNER_ID,
                            MEMBER_ID,
                        ),
                    )
        except BaseException as error:  # pragma: no cover - surfaced below
            failures.append(error)

    def settlement() -> None:
        try:
            if not writer_has_account.wait(timeout=2):
                raise RuntimeError("writer session did not acquire the account lock")
            with psycopg.connect(DATABASE_URL) as connection:
                with connection.cursor() as cursor:
                    authenticated(cursor)
                    settlement_started.set()
                    cursor.execute(
                        """
                        select public.settle_member_balance(
                          %s, %s, %s, 2500, now(),
                          'concurrency-settlement-0001', 'Concurrent repayment'
                        )
                        """,
                        (HOUSEHOLD_ID, MEMBER_ID, ACCOUNT_ID),
                    )
        except BaseException as error:  # pragma: no cover - surfaced below
            failures.append(error)

    try:
        writer_thread = threading.Thread(target=writer, name="ledger-writer")
        settlement_thread = threading.Thread(target=settlement, name="settlement-writer")
        writer_thread.start()
        settlement_thread.start()
        writer_thread.join(timeout=10)
        settlement_thread.join(timeout=10)
        if writer_thread.is_alive() or settlement_thread.is_alive():
            raise RuntimeError("concurrency contract timed out")
        if failures:
            raise RuntimeError("concurrency contract failed") from failures[0]
        print("daily-use concurrency contract passed")
    finally:
        cleanup_fixture()


if __name__ == "__main__":
    main()
