from __future__ import annotations

import argparse
from pathlib import Path

import db_pipeline
import env_bootstrap


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest selected obituary scraper output JSON into SQLite app DB.")
    parser.add_argument(
        "--input",
        type=str,
        default=str(db_pipeline.SELECTED_OUTPUT_PATH),
        help="Path to selected scraper output JSON (default: obituaries_selected_pages.json)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Optional SQLite DB path override (default: data/app.db or APP_DB_PATH)",
    )
    parser.add_argument(
        "--started-at",
        type=str,
        default=None,
        help="Optional scrape started timestamp (ISO-8601)",
    )
    parser.add_argument(
        "--finished-at",
        type=str,
        default=None,
        help="Optional scrape finished timestamp (ISO-8601)",
    )
    return parser.parse_args()


def main() -> None:
    env_bootstrap.load_env_file()
    args = parse_args()
    provider = db_pipeline.get_db_provider()
    effective_db_path = Path(args.db_path).expanduser().resolve() if args.db_path else None
    result = db_pipeline.ingest_selected_output_file(
        output_path=Path(args.input),
        db_path=effective_db_path,
        started_at=args.started_at,
        finished_at=args.finished_at,
    )

    print(f"{provider.capitalize()} ingestion complete")
    print(f"  Run ID: {result['runId']}")
    print(f"  Obituaries upserted: {result['obituariesUpserted']}")
    print(f"  Queue records seeded: {result['queueRecordsSeeded']}")
    print(f"  Sources tracked: {result['sourcesTracked']}")
    print(f"  Status: {result['status']}")
    if provider == "postgres":
        print("  Target: DB_CONNECTION_STRING/DATABASE_URL")
    else:
        print(f"  DB path: {effective_db_path or db_pipeline.get_db_path()}")


if __name__ == "__main__":
    main()
