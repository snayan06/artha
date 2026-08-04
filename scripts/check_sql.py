from __future__ import annotations

from pathlib import Path

from pglast import parse_sql


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    sql_files = sorted((root / "supabase").glob("**/*.sql"))
    if not sql_files:
        raise SystemExit("No Supabase SQL files found")
    for path in sql_files:
        parse_sql(path.read_text(encoding="utf-8"))
        print(f"parsed {path.relative_to(root)}")


if __name__ == "__main__":
    main()
