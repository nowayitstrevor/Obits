from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

import psycopg
from psycopg import sql

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from env_bootstrap import load_env_file


TABLES_IN_ORDER = [
    "obituaries",
    "post_queue",
    "queue_transition_audit",
    "publish_worker_status",
    "runtime_locks",
    "publish_preflight_runs",
    "scrape_runs",
    "scrape_source_status",
    "scrape_source_latest",
]

PK_COLUMNS: dict[str, list[str]] = {
    "obituaries": ["id"],
    "post_queue": ["obituary_id"],
    "queue_transition_audit": ["id"],
    "publish_worker_status": ["id"],
    "runtime_locks": ["lock_name"],
    "publish_preflight_runs": ["id"],
    "scrape_runs": ["id"],
    "scrape_source_status": ["id"],
    "scrape_source_latest": ["source_key"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-time backfill from SQLite app DB into PostgreSQL.")
    parser.add_argument(
        "--sqlite-path",
        default="data/app.db",
        help="Path to source SQLite DB (default: data/app.db)",
    )
    parser.add_argument(
        "--postgres-url",
        default="",
        help="Postgres URL override (default: DB_CONNECTION_STRING or DATABASE_URL env var)",
    )
    parser.add_argument(
        "--truncate-target",
        action="store_true",
        help="Truncate target tables before backfill (uses TRUNCATE ... RESTART IDENTITY CASCADE)",
    )
    parser.add_argument(
        "--tables",
        default=",".join(TABLES_IN_ORDER),
        help="Comma-separated table list to backfill in order",
    )
    return parser.parse_args()


def _table_columns_sqlite(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [str(row[1]) for row in rows]


def _table_columns_postgres(conn: psycopg.Connection, table_name: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table_name,),
        )
        rows = cur.fetchall()
    return [str(row[0]) for row in rows]


def _fetch_sqlite_rows(conn: sqlite3.Connection, table_name: str, columns: list[str]) -> list[tuple]:
    query = f"SELECT {', '.join(columns)} FROM {table_name}"
    cur = conn.execute(query)
    return [tuple(row[col] for col in columns) for row in cur.fetchall()]


def _upsert_rows(
    conn: psycopg.Connection,
    table_name: str,
    columns: list[str],
    rows: list[tuple],
) -> int:
    if not rows:
        return 0

    pk_cols = PK_COLUMNS.get(table_name, [])
    if not pk_cols:
        raise RuntimeError(f"Missing PK mapping for table: {table_name}")

    non_pk_cols = [col for col in columns if col not in pk_cols]

    insert_stmt = sql.SQL("INSERT INTO {table} ({cols}) VALUES ({vals})").format(
        table=sql.Identifier(table_name),
        cols=sql.SQL(", ").join(sql.Identifier(col) for col in columns),
        vals=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )

    if non_pk_cols:
        conflict_stmt = sql.SQL(" ON CONFLICT ({pk}) DO UPDATE SET {updates}").format(
            pk=sql.SQL(", ").join(sql.Identifier(col) for col in pk_cols),
            updates=sql.SQL(", ").join(
                sql.SQL("{col} = EXCLUDED.{col}").format(col=sql.Identifier(col)) for col in non_pk_cols
            ),
        )
    else:
        conflict_stmt = sql.SQL(" ON CONFLICT ({pk}) DO NOTHING").format(
            pk=sql.SQL(", ").join(sql.Identifier(col) for col in pk_cols)
        )

    query = insert_stmt + conflict_stmt
    with conn.cursor() as cur:
        cur.executemany(query, rows)
    return len(rows)


def _count_table(conn: psycopg.Connection, table_name: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("SELECT COUNT(*) FROM {table}").format(table=sql.Identifier(table_name))
        )
        row = cur.fetchone()
    return int(row[0]) if row else 0


def _truncate_tables(conn: psycopg.Connection, tables: list[str]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE").format(
                tables=sql.SQL(", ").join(sql.Identifier(t) for t in tables)
            )
        )


def main() -> int:
    load_env_file()
    args = parse_args()

    sqlite_path = Path(args.sqlite_path).expanduser().resolve()
    if not sqlite_path.exists():
        print(f"ERROR: SQLite database not found at: {sqlite_path}")
        return 1

    pg_url = (
        str(args.postgres_url).strip()
        or str(os.environ.get("DB_CONNECTION_STRING", "")).strip()
        or str(os.environ.get("DATABASE_URL", "")).strip()
    )
    if not pg_url:
        print("ERROR: Missing Postgres URL. Set DB_CONNECTION_STRING or pass --postgres-url.")
        return 1

    selected_tables = [t.strip() for t in str(args.tables).split(",") if t.strip()]
    invalid_tables = [t for t in selected_tables if t not in TABLES_IN_ORDER]
    if invalid_tables:
        print(f"ERROR: Unsupported table(s): {', '.join(invalid_tables)}")
        return 1

    print(f"Using SQLite source: {sqlite_path}")
    print("Connecting to PostgreSQL target...")

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    try:
        with psycopg.connect(pg_url) as pg_conn:
            with pg_conn.transaction():
                if args.truncate_target:
                    print("Truncating target tables...")
                    _truncate_tables(pg_conn, list(reversed(selected_tables)))

                for table_name in selected_tables:
                    sqlite_cols = _table_columns_sqlite(sqlite_conn, table_name)
                    pg_cols = _table_columns_postgres(pg_conn, table_name)
                    common_cols = [c for c in sqlite_cols if c in set(pg_cols)]

                    if not common_cols:
                        raise RuntimeError(f"No shared columns for table: {table_name}")

                    rows = _fetch_sqlite_rows(sqlite_conn, table_name, common_cols)
                    copied = _upsert_rows(pg_conn, table_name, common_cols, rows)
                    target_count = _count_table(pg_conn, table_name)
                    print(
                        f"{table_name}: sqlite_rows={len(rows)} upserted={copied} postgres_rows={target_count}"
                    )

        print("Backfill complete.")
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1
    finally:
        sqlite_conn.close()


if __name__ == "__main__":
    sys.exit(main())