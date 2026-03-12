from __future__ import annotations

import json
import os
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "app.db"
SELECTED_OUTPUT_PATH = BASE_DIR / "obituaries_selected_pages.json"

QUEUE_STATUSES = {"new", "staged", "scheduled", "posted", "archived"}
ALLOWED_QUEUE_TRANSITIONS: dict[str, set[str]] = {
    "new": {"staged"},
    "staged": {"scheduled", "new"},
    "scheduled": {"posted", "staged"},
    "posted": {"archived"},
    "archived": set(),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db_path() -> Path:
    configured = os.environ.get("APP_DB_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_DB_PATH


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS obituaries (
            id TEXT PRIMARY KEY,
            source_key TEXT NOT NULL,
            source_name TEXT NOT NULL,
            listing_url TEXT,
            obituary_url TEXT NOT NULL,
            name TEXT,
            birth_date TEXT,
            death_date TEXT,
            age INTEGER,
            summary TEXT,
            photo_url TEXT,
            scraped_at TEXT,
            raw_hash TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(obituary_url)
        );

        CREATE INDEX IF NOT EXISTS idx_obituaries_source_key ON obituaries(source_key);
        CREATE INDEX IF NOT EXISTS idx_obituaries_scraped_at ON obituaries(scraped_at);
        CREATE INDEX IF NOT EXISTS idx_obituaries_death_date ON obituaries(death_date);

        CREATE TABLE IF NOT EXISTS post_queue (
            obituary_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'new',
            scheduled_for TEXT,
            posted_at TEXT,
            archived_at TEXT,
            facebook_post_id TEXT,
            comment_url TEXT,
            last_error TEXT,
            retry_count INTEGER NOT NULL DEFAULT 0,
            retry_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(obituary_id) REFERENCES obituaries(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_post_queue_status ON post_queue(status);
        CREATE INDEX IF NOT EXISTS idx_post_queue_scheduled_for ON post_queue(scheduled_for);

        CREATE TABLE IF NOT EXISTS queue_transition_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            obituary_id TEXT NOT NULL,
            from_status TEXT NOT NULL,
            to_status TEXT NOT NULL,
            action_at TEXT NOT NULL,
            initiated_by TEXT,
            metadata_json TEXT,
            FOREIGN KEY(obituary_id) REFERENCES post_queue(obituary_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_queue_transition_audit_obituary_id ON queue_transition_audit(obituary_id);
        CREATE INDEX IF NOT EXISTS idx_queue_transition_audit_action_at ON queue_transition_audit(action_at);

        CREATE TABLE IF NOT EXISTS publish_worker_status (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            state TEXT NOT NULL DEFAULT 'idle',
            message TEXT,
            started_at TEXT,
            finished_at TEXT,
            processed INTEGER NOT NULL DEFAULT 0,
            published INTEGER NOT NULL DEFAULT 0,
            failed INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            last_run_json TEXT,
            worker_mode TEXT,
            worker_enabled INTEGER NOT NULL DEFAULT 0,
            poll_seconds INTEGER NOT NULL DEFAULT 300,
            heartbeat_at TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runtime_locks (
            lock_name TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            metadata_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_runtime_locks_expires_at ON runtime_locks(expires_at);

        CREATE TABLE IF NOT EXISTS publish_preflight_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TEXT NOT NULL,
            initiated_by TEXT,
            provider TEXT,
            deep_probe_requested INTEGER NOT NULL DEFAULT 0,
            strict_mode INTEGER NOT NULL DEFAULT 1,
            ok INTEGER NOT NULL DEFAULT 0,
            status_code INTEGER NOT NULL DEFAULT 200,
            passed_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            warning_count INTEGER NOT NULL DEFAULT 0,
            error TEXT,
            failed_checks_json TEXT,
            warning_checks_json TEXT,
            payload_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_publish_preflight_runs_run_at ON publish_preflight_runs(run_at);

        CREATE TABLE IF NOT EXISTS scrape_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_at TEXT,
            started_at TEXT,
            finished_at TEXT,
            source_count INTEGER NOT NULL,
            successful_sources INTEGER NOT NULL,
            failed_sources INTEGER NOT NULL,
            total_obituaries INTEGER NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_scrape_runs_created_at ON scrape_runs(created_at);

        CREATE TABLE IF NOT EXISTS scrape_source_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            source_key TEXT NOT NULL,
            source_name TEXT NOT NULL,
            status TEXT NOT NULL,
            freshness_status TEXT NOT NULL,
            freshness_reason TEXT,
            has_new_obituaries INTEGER NOT NULL DEFAULT 0,
            last_known_found INTEGER,
            needs_reprogramming INTEGER NOT NULL DEFAULT 0,
            listing_url TEXT,
            pages_discovered INTEGER NOT NULL,
            obituaries_scraped INTEGER NOT NULL,
            duration_ms INTEGER NOT NULL,
            error TEXT,
            last_known_obituary_id TEXT,
            last_known_obituary_url TEXT,
            checked_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES scrape_runs(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_scrape_source_status_run_id ON scrape_source_status(run_id);
        CREATE INDEX IF NOT EXISTS idx_scrape_source_status_source_key ON scrape_source_status(source_key);
        CREATE INDEX IF NOT EXISTS idx_scrape_source_status_checked_at ON scrape_source_status(checked_at);

        CREATE TABLE IF NOT EXISTS scrape_source_latest (
            source_key TEXT PRIMARY KEY,
            source_name TEXT NOT NULL,
            status TEXT NOT NULL,
            freshness_status TEXT NOT NULL,
            freshness_reason TEXT,
            has_new_obituaries INTEGER NOT NULL DEFAULT 0,
            last_known_found INTEGER,
            needs_reprogramming INTEGER NOT NULL DEFAULT 0,
            consecutive_no_new_runs INTEGER NOT NULL DEFAULT 0,
            last_new_obituary_id TEXT,
            last_new_obituary_url TEXT,
            last_new_obituary_at TEXT,
            listing_url TEXT,
            obituaries_scraped INTEGER NOT NULL,
            duration_ms INTEGER NOT NULL,
            error TEXT,
            run_id INTEGER NOT NULL,
            checked_at TEXT NOT NULL,
            FOREIGN KEY(run_id) REFERENCES scrape_runs(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_scrape_source_latest_freshness ON scrape_source_latest(freshness_status);
        """
    )

    _ensure_optional_column(conn, "scrape_source_status", "freshness_reason", "TEXT")
    _ensure_optional_column(conn, "scrape_source_status", "has_new_obituaries", "INTEGER NOT NULL DEFAULT 0")
    _ensure_optional_column(conn, "scrape_source_status", "last_known_found", "INTEGER")
    _ensure_optional_column(conn, "scrape_source_status", "needs_reprogramming", "INTEGER NOT NULL DEFAULT 0")

    _ensure_optional_column(conn, "post_queue", "override_name", "TEXT")
    _ensure_optional_column(conn, "post_queue", "override_birth_date", "TEXT")
    _ensure_optional_column(conn, "post_queue", "override_death_date", "TEXT")
    _ensure_optional_column(conn, "post_queue", "override_reason", "TEXT")
    _ensure_optional_column(conn, "post_queue", "override_updated_at", "TEXT")
    _ensure_optional_column(conn, "post_queue", "override_updated_by", "TEXT")
    _ensure_optional_column(conn, "post_queue", "retry_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_optional_column(conn, "post_queue", "retry_at", "TEXT")
    _ensure_optional_index(conn, "idx_post_queue_retry_at", "post_queue", "retry_at")

    _ensure_optional_column(conn, "scrape_source_latest", "freshness_reason", "TEXT")
    _ensure_optional_column(conn, "scrape_source_latest", "has_new_obituaries", "INTEGER NOT NULL DEFAULT 0")
    _ensure_optional_column(conn, "scrape_source_latest", "last_known_found", "INTEGER")
    _ensure_optional_column(conn, "scrape_source_latest", "needs_reprogramming", "INTEGER NOT NULL DEFAULT 0")
    _ensure_optional_column(conn, "scrape_source_latest", "consecutive_no_new_runs", "INTEGER NOT NULL DEFAULT 0")
    _ensure_optional_column(conn, "scrape_source_latest", "last_new_obituary_id", "TEXT")
    _ensure_optional_column(conn, "scrape_source_latest", "last_new_obituary_url", "TEXT")
    _ensure_optional_column(conn, "scrape_source_latest", "last_new_obituary_at", "TEXT")

    conn.commit()


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def _ensure_optional_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_definition: str) -> None:
    columns = _table_columns(conn, table_name)
    if column_name in columns:
        return
    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def _ensure_optional_index(conn: sqlite3.Connection, index_name: str, table_name: str, column_name: str) -> None:
    columns = _table_columns(conn, table_name)
    if column_name not in columns:
        return
    conn.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}({column_name})")


def _as_bool_int(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def _as_iso(value: str | None) -> str | None:
    if not value:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    return candidate


def _normalize_override_text(value: Any) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    return candidate


def _clean_person_name(value: Any, source_name: Any = None) -> str | None:
    if value is None:
        return None

    candidate = str(value).strip()
    if not candidate:
        return None

    date_fragment = (
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},?\s+\d{4}"
        r"|\d{1,2}[/-]\d{1,2}[/-]\d{4}"
        r"|\d{4}-\d{1,2}-\d{1,2}"
    )

    cleaned = re.sub(r"\s+", " ", candidate).strip(" \t\r\n,;:-")
    cleaned = re.sub(r"^(?:obituary\s+for|obituary\s+of|in\s+loving\s+memory\s+of)\s+", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*\|\s*\d{4}\s*-\s*\d{4}\s*\|\s*obituary\b.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"^obituary\s*\|\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*\|\s*obituary\b.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(rf"\s+obituary\s+{date_fragment}\b.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(
        r"\s*(?:\||[-–—])\s*[^|]*\b(funeral\s+home|funeral\s+services|memorial|mortuary|chapel|cremation|crematorium|cemetery)\b.*$",
        "",
        cleaned,
        flags=re.I,
    )

    normalized_source = str(source_name).strip() if source_name is not None else ""
    if normalized_source:
        cleaned = re.sub(
            rf"\s*(?:\||[-–—])\s*{re.escape(normalized_source)}\s*$",
            "",
            cleaned,
            flags=re.I,
        )

    cleaned = re.sub(r"\s*(?:\||[-–—])\s*obituary\s*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" \t\r\n,;:-")
    return cleaned or None


def _sanitize_feed_row_names(row: dict[str, Any]) -> dict[str, Any]:
    source_name = row.get("source_name")
    row["name"] = _clean_person_name(row.get("name"), source_name=source_name)
    row["effective_name"] = _clean_person_name(row.get("effective_name"), source_name=source_name) or row.get("name")
    return row


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def acquire_runtime_lock(
    conn: sqlite3.Connection,
    lock_name: str,
    owner_id: str,
    ttl_seconds: int = 300,
    metadata: dict[str, Any] | None = None,
) -> bool:
    ensure_schema(conn)

    normalized_lock = str(lock_name or "").strip()
    normalized_owner = str(owner_id or "").strip()
    if not normalized_lock:
        raise ValueError("lock_name is required.")
    if not normalized_owner:
        raise ValueError("owner_id is required.")

    now_dt = datetime.now(timezone.utc)
    now_value = now_dt.isoformat()
    ttl = max(30, _to_int(ttl_seconds, default=300))
    expires_value = (now_dt + timedelta(seconds=ttl)).isoformat()
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False) if metadata is not None else None

    conn.execute("DELETE FROM runtime_locks WHERE expires_at <= ?", (now_value,))

    cursor = conn.execute(
        """
        INSERT INTO runtime_locks (lock_name, owner_id, acquired_at, expires_at, metadata_json)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(lock_name) DO UPDATE SET
            owner_id = excluded.owner_id,
            acquired_at = excluded.acquired_at,
            expires_at = excluded.expires_at,
            metadata_json = excluded.metadata_json
        WHERE runtime_locks.expires_at <= excluded.acquired_at
        """,
        (
            normalized_lock,
            normalized_owner,
            now_value,
            expires_value,
            metadata_json,
        ),
    )
    conn.commit()
    return int(cursor.rowcount or 0) > 0


def release_runtime_lock(
    conn: sqlite3.Connection,
    lock_name: str,
    owner_id: str | None = None,
) -> bool:
    ensure_schema(conn)

    normalized_lock = str(lock_name or "").strip()
    if not normalized_lock:
        return False

    normalized_owner = str(owner_id or "").strip()
    if normalized_owner:
        cursor = conn.execute(
            "DELETE FROM runtime_locks WHERE lock_name = ? AND owner_id = ?",
            (normalized_lock, normalized_owner),
        )
    else:
        cursor = conn.execute(
            "DELETE FROM runtime_locks WHERE lock_name = ?",
            (normalized_lock,),
        )
    conn.commit()
    return int(cursor.rowcount or 0) > 0


def get_publish_worker_status(conn: sqlite3.Connection) -> dict[str, Any]:
    ensure_schema(conn)

    row = conn.execute(
        """
        SELECT
            state,
            message,
            started_at,
            finished_at,
            processed,
            published,
            failed,
            last_error,
            last_run_json,
            worker_mode,
            worker_enabled,
            poll_seconds,
            heartbeat_at,
            updated_at
        FROM publish_worker_status
        WHERE id = 1
        LIMIT 1
        """
    ).fetchone()

    if not row:
        return {
            "state": "idle",
            "message": "No publish run started yet.",
            "startedAt": None,
            "finishedAt": None,
            "processed": 0,
            "published": 0,
            "failed": 0,
            "lastError": None,
            "lastRun": None,
            "workerMode": None,
            "workerEnabled": False,
            "pollSeconds": 300,
            "heartbeatAt": None,
            "updatedAt": None,
        }

    raw = dict(row)
    parsed_last_run: dict[str, Any] | None = None
    if raw.get("last_run_json"):
        try:
            candidate = json.loads(str(raw["last_run_json"]))
            if isinstance(candidate, dict):
                parsed_last_run = candidate
        except Exception:
            parsed_last_run = None

    return {
        "state": str(raw.get("state") or "idle"),
        "message": str(raw.get("message") or ""),
        "startedAt": raw.get("started_at"),
        "finishedAt": raw.get("finished_at"),
        "processed": _to_int(raw.get("processed"), default=0),
        "published": _to_int(raw.get("published"), default=0),
        "failed": _to_int(raw.get("failed"), default=0),
        "lastError": raw.get("last_error"),
        "lastRun": parsed_last_run,
        "workerMode": raw.get("worker_mode"),
        "workerEnabled": bool(raw.get("worker_enabled")),
        "pollSeconds": max(30, _to_int(raw.get("poll_seconds"), default=300)),
        "heartbeatAt": raw.get("heartbeat_at"),
        "updatedAt": raw.get("updated_at"),
    }


def update_publish_worker_status(conn: sqlite3.Connection, updates: dict[str, Any]) -> dict[str, Any]:
    ensure_schema(conn)

    current = get_publish_worker_status(conn)
    merged = {**current}
    for key, value in (updates or {}).items():
        merged[key] = value

    poll_seconds = max(30, _to_int(merged.get("pollSeconds"), default=300))
    updated_at = now_iso()
    last_run_obj = merged.get("lastRun") if isinstance(merged.get("lastRun"), dict) else None
    last_run_json = json.dumps(last_run_obj, ensure_ascii=False) if last_run_obj is not None else None

    conn.execute(
        """
        INSERT INTO publish_worker_status (
            id,
            state,
            message,
            started_at,
            finished_at,
            processed,
            published,
            failed,
            last_error,
            last_run_json,
            worker_mode,
            worker_enabled,
            poll_seconds,
            heartbeat_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            state = excluded.state,
            message = excluded.message,
            started_at = excluded.started_at,
            finished_at = excluded.finished_at,
            processed = excluded.processed,
            published = excluded.published,
            failed = excluded.failed,
            last_error = excluded.last_error,
            last_run_json = excluded.last_run_json,
            worker_mode = excluded.worker_mode,
            worker_enabled = excluded.worker_enabled,
            poll_seconds = excluded.poll_seconds,
            heartbeat_at = excluded.heartbeat_at,
            updated_at = excluded.updated_at
        """,
        (
            1,
            str(merged.get("state") or "idle"),
            str(merged.get("message") or ""),
            merged.get("startedAt"),
            merged.get("finishedAt"),
            _to_int(merged.get("processed"), default=0),
            _to_int(merged.get("published"), default=0),
            _to_int(merged.get("failed"), default=0),
            merged.get("lastError"),
            last_run_json,
            merged.get("workerMode"),
            1 if bool(merged.get("workerEnabled")) else 0,
            poll_seconds,
            merged.get("heartbeatAt"),
            updated_at,
        ),
    )
    conn.commit()
    return get_publish_worker_status(conn)


def heartbeat_publish_worker(
    conn: sqlite3.Connection,
    *,
    worker_mode: str,
    worker_enabled: bool,
    poll_seconds: int,
    message: str | None = None,
) -> dict[str, Any]:
    now_value = now_iso()
    return update_publish_worker_status(
        conn,
        {
            "workerMode": str(worker_mode or "worker").strip() or "worker",
            "workerEnabled": bool(worker_enabled),
            "pollSeconds": max(30, _to_int(poll_seconds, default=300)),
            "heartbeatAt": now_value,
            "message": message,
        },
    )


def _safe_json_dumps(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return None


def record_publish_preflight_run(
    conn: sqlite3.Connection,
    *,
    body: dict[str, Any],
    status_code: int,
    initiated_by: str,
) -> dict[str, Any]:
    ensure_schema(conn)

    payload = body if isinstance(body, dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []

    failed_checks = [
        str(item.get("name") or "unknown")
        for item in checks
        if isinstance(item, dict) and (not bool(item.get("ok"))) and str(item.get("severity") or "error") != "warning"
    ]
    warning_checks = [
        str(item.get("name") or "unknown")
        for item in checks
        if isinstance(item, dict) and (not bool(item.get("ok"))) and str(item.get("severity") or "error") == "warning"
    ]

    run_at = now_iso()
    normalized_initiated_by = str(initiated_by or "publish_preflight").strip() or "publish_preflight"
    provider = str(payload.get("provider") or "").strip() or None
    deep_probe_requested = bool(payload.get("deepProbeRequested"))
    strict_mode = bool(payload.get("strictMode", True))
    ok = bool(payload.get("ok")) and int(status_code) < 400

    cursor = conn.execute(
        """
        INSERT INTO publish_preflight_runs (
            run_at,
            initiated_by,
            provider,
            deep_probe_requested,
            strict_mode,
            ok,
            status_code,
            passed_count,
            failed_count,
            warning_count,
            error,
            failed_checks_json,
            warning_checks_json,
            payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_at,
            normalized_initiated_by,
            provider,
            1 if deep_probe_requested else 0,
            1 if strict_mode else 0,
            1 if ok else 0,
            int(status_code),
            _to_int(summary.get("passed"), default=0),
            _to_int(summary.get("failed"), default=0),
            _to_int(summary.get("warnings"), default=0),
            str(payload.get("error") or "").strip() or None,
            _safe_json_dumps(failed_checks),
            _safe_json_dumps(warning_checks),
            _safe_json_dumps(payload),
        ),
    )
    conn.commit()

    created_id = _to_int(cursor.lastrowid, default=0)
    row = conn.execute(
        """
        SELECT
            id,
            run_at,
            initiated_by,
            provider,
            deep_probe_requested,
            strict_mode,
            ok,
            status_code,
            passed_count,
            failed_count,
            warning_count,
            error,
            failed_checks_json,
            warning_checks_json
        FROM publish_preflight_runs
        WHERE id = ?
        LIMIT 1
        """,
        (created_id,),
    ).fetchone()
    return _parse_publish_preflight_row(row) if row else {}


def _parse_publish_preflight_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if not row:
        return {}

    raw = dict(row)
    failed_checks: list[str] = []
    warning_checks: list[str] = []

    for key, target in (("failed_checks_json", failed_checks), ("warning_checks_json", warning_checks)):
        blob = raw.get(key)
        if not blob:
            continue
        try:
            parsed = json.loads(str(blob))
            if isinstance(parsed, list):
                target.extend(str(item) for item in parsed if str(item).strip())
        except Exception:
            continue

    return {
        "id": _to_int(raw.get("id"), default=0),
        "runAt": raw.get("run_at"),
        "initiatedBy": raw.get("initiated_by"),
        "provider": raw.get("provider"),
        "deepProbeRequested": bool(raw.get("deep_probe_requested")),
        "strictMode": bool(raw.get("strict_mode")),
        "ok": bool(raw.get("ok")),
        "statusCode": _to_int(raw.get("status_code"), default=200),
        "passed": _to_int(raw.get("passed_count"), default=0),
        "failed": _to_int(raw.get("failed_count"), default=0),
        "warnings": _to_int(raw.get("warning_count"), default=0),
        "error": raw.get("error"),
        "failedChecks": failed_checks,
        "warningChecks": warning_checks,
    }


def get_latest_publish_preflight_run(conn: sqlite3.Connection) -> dict[str, Any] | None:
    ensure_schema(conn)

    row = conn.execute(
        """
        SELECT
            id,
            run_at,
            initiated_by,
            provider,
            deep_probe_requested,
            strict_mode,
            ok,
            status_code,
            passed_count,
            failed_count,
            warning_count,
            error,
            failed_checks_json,
            warning_checks_json
        FROM publish_preflight_runs
        ORDER BY run_at DESC, id DESC
        LIMIT 1
        """
    ).fetchone()

    if not row:
        return None
    return _parse_publish_preflight_row(row)


def _parse_iso_datetime(value: str) -> datetime:
    candidate = str(value or "").strip()
    if not candidate:
        raise ValueError("scheduledFor is required for scheduled status.")

    normalized = candidate[:-1] + "+00:00" if candidate.endswith("Z") else candidate
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ValueError("scheduledFor must be a valid ISO-8601 timestamp.") from error

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)

    return parsed


def _parse_flexible_datetime(value: str | None) -> datetime | None:
    candidate = str(value or "").strip()
    if not candidate:
        return None

    attempts = [candidate]
    if candidate.endswith("Z"):
        attempts.append(candidate[:-1] + "+00:00")

    for item in attempts:
        try:
            parsed = datetime.fromisoformat(item)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                parsed = parsed.astimezone(timezone.utc)
            return parsed
        except ValueError:
            continue

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            parsed = datetime.strptime(candidate, fmt)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def _load_existing_state(conn: sqlite3.Connection) -> tuple[dict[str, set[str]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    existing_ids_by_source: dict[str, set[str]] = defaultdict(set)
    for row in conn.execute("SELECT source_key, id FROM obituaries").fetchall():
        source_key = str(row[0] or "").strip()
        obit_id = str(row[1] or "").strip()
        if source_key and obit_id:
            existing_ids_by_source[source_key].add(obit_id)

    latest_obit_by_source: dict[str, dict[str, Any]] = {}
    latest_rows = conn.execute(
        """
        SELECT
            source_key,
            id,
            obituary_url,
            death_date,
            scraped_at,
            updated_at
        FROM obituaries
        ORDER BY source_key ASC, COALESCE(death_date, scraped_at, updated_at) DESC
        """
    ).fetchall()
    for row in latest_rows:
        source_key = str(row[0] or "").strip()
        if not source_key or source_key in latest_obit_by_source:
            continue
        latest_obit_by_source[source_key] = {
            "id": row[1],
            "obituary_url": row[2],
            "death_date": row[3],
            "scraped_at": row[4],
            "updated_at": row[5],
        }

    latest_source_rows = conn.execute(
        """
        SELECT
            source_key,
            source_name,
            status,
            freshness_status,
            freshness_reason,
            has_new_obituaries,
            last_known_found,
            needs_reprogramming,
            consecutive_no_new_runs,
            last_new_obituary_id,
            last_new_obituary_url,
            last_new_obituary_at,
            listing_url,
            obituaries_scraped,
            duration_ms,
            error,
            run_id,
            checked_at
        FROM scrape_source_latest
        """
    ).fetchall()
    latest_source_by_key = {str(row[0]): dict(row) for row in latest_source_rows if row[0]}

    return dict(existing_ids_by_source), latest_obit_by_source, latest_source_by_key


def _compute_source_freshness(
    source_status: str,
    has_new_obituaries: bool,
    last_known_found: bool | None,
    consecutive_no_new_runs: int,
    no_new_runs_red_threshold: int,
    source_error: str | None = None,
) -> tuple[str, bool, str]:
    error_text = str(source_error or "").strip().lower()
    transient_outage = bool(
        error_text
        and (
            "http error 530" in error_text
            or " 530 " in f" {error_text} "
            or "cloudflare" in error_text
            or "timed out" in error_text
            or "connection reset" in error_text
            or "temporary failure in name resolution" in error_text
            or "name or service not known" in error_text
        )
    )

    if source_status == "error":
        if transient_outage:
            return "yellow", False, "Source website is temporarily unavailable; scraper will retry automatically."
        return "red", True, "Scrape failed."

    if last_known_found is False:
        return "red", True, "Last-known obituary was not found in latest scrape output."

    if source_status == "skipped":
        return "yellow", False, "Source was skipped this run (safe mode or disabled path)."

    if has_new_obituaries:
        return "green", False, "New obituaries detected."

    if source_status == "no-data":
        return "yellow", False, "No obituary pages were returned for this source."

    if source_status == "ok":
        if last_known_found is True:
            if consecutive_no_new_runs >= max(1, no_new_runs_red_threshold):
                return "yellow", False, f"No new obituaries for {consecutive_no_new_runs} consecutive runs."
            return "green", False, "Continuity check passed (last-known obituary still found)."
        return "yellow", False, "Scrape succeeded but continuity baseline is not established yet."

    return "yellow", False, "Status is indeterminate; monitor this source."


def _compute_freshness(source_status: str, obituaries_scraped: int) -> str:
    if source_status == "error":
        return "red"
    if source_status == "no-data":
        return "yellow"
    if source_status == "ok" and obituaries_scraped > 0:
        return "green"
    return "yellow"


def _upsert_obituary(conn: sqlite3.Connection, item: dict[str, Any], timestamp: str) -> None:
    cleaned_name = _clean_person_name(item.get("name"), source_name=item.get("sourceName"))

    conn.execute(
        """
        INSERT INTO obituaries (
            id, source_key, source_name, listing_url, obituary_url, name,
            birth_date, death_date, age, summary, photo_url, scraped_at,
            raw_hash, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            source_key = excluded.source_key,
            source_name = excluded.source_name,
            listing_url = excluded.listing_url,
            obituary_url = excluded.obituary_url,
            name = excluded.name,
            birth_date = excluded.birth_date,
            death_date = excluded.death_date,
            age = excluded.age,
            summary = excluded.summary,
            photo_url = excluded.photo_url,
            scraped_at = excluded.scraped_at,
            raw_hash = excluded.raw_hash,
            updated_at = excluded.updated_at
        """,
        (
            item.get("id"),
            item.get("sourceKey"),
            item.get("sourceName"),
            item.get("listingUrl"),
            item.get("obituaryUrl"),
            cleaned_name,
            item.get("birthDate"),
            item.get("deathDate"),
            item.get("age"),
            item.get("summary"),
            item.get("photoUrl"),
            item.get("scrapedAt"),
            item.get("id"),
            timestamp,
            timestamp,
        ),
    )


def _ensure_post_queue_record(conn: sqlite3.Connection, obituary_id: str, timestamp: str) -> None:
    conn.execute(
        """
        INSERT INTO post_queue (obituary_id, status, created_at, updated_at)
        VALUES (?, 'new', ?, ?)
        ON CONFLICT(obituary_id) DO NOTHING
        """,
        (obituary_id, timestamp, timestamp),
    )


def ingest_selected_output(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
    started_at: str | None = None,
    finished_at: str | None = None,
) -> dict[str, Any]:
    ensure_schema(conn)

    existing_ids_by_source, latest_obit_by_source, latest_source_by_key = _load_existing_state(conn)

    generated_at = payload.get("generatedAt")
    obituaries = payload.get("obituaries", []) or []
    report = payload.get("scrapeReport", {}) or {}
    sources = report.get("sources", []) or []
    no_new_runs_red_threshold = int(os.environ.get("SOURCE_NO_NEW_RUNS_RED", "3") or 3)

    payload_records_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in obituaries:
        if not isinstance(item, dict):
            continue
        source_key = str(item.get("sourceKey") or "").strip()
        obit_id = str(item.get("id") or "").strip()
        obit_url = str(item.get("obituaryUrl") or "").strip()
        if not source_key or not obit_id or not obit_url:
            continue
        payload_records_by_source[source_key].append(item)

    timestamp = now_iso()
    successful_sources = int(report.get("successfulSources", 0) or 0)
    failed_sources = int(report.get("failedSources", 0) or 0)
    total_obituaries = int(report.get("totalObituaries", len(obituaries)) or 0)

    run_status = "ok" if failed_sources == 0 else "error"
    run_message = f"Ingested {len(obituaries)} obituaries from selected scraper output"

    cursor = conn.execute(
        """
        INSERT INTO scrape_runs (
            generated_at, started_at, finished_at, source_count,
            successful_sources, failed_sources, total_obituaries,
            status, message, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            generated_at,
            started_at,
            finished_at,
            len(sources),
            successful_sources,
            failed_sources,
            total_obituaries,
            run_status,
            run_message,
            timestamp,
        ),
    )
    run_id = int(cursor.lastrowid)

    upserted_obituaries = 0
    seeded_queue_records = 0

    for item in obituaries:
        if not isinstance(item, dict):
            continue
        obituary_id = item.get("id")
        obituary_url = item.get("obituaryUrl")
        if not obituary_id or not obituary_url:
            continue

        _upsert_obituary(conn, item, timestamp=timestamp)
        upserted_obituaries += 1

        before = conn.total_changes
        _ensure_post_queue_record(conn, obituary_id=obituary_id, timestamp=timestamp)
        if conn.total_changes > before:
            seeded_queue_records += 1

    for source in sources:
        if not isinstance(source, dict):
            continue

        source_key = str(source.get("sourceKey") or "").strip()
        if not source_key:
            continue

        source_name = str(source.get("source") or source.get("sourceName") or source_key)
        source_status = str(source.get("status") or "unknown")
        obits_scraped = int(source.get("obituariesScraped", 0) or 0)
        duration_ms = int(source.get("durationMs", 0) or 0)
        pages_discovered = int(source.get("pagesDiscovered", 0) or 0)
        listing_url = source.get("listingUrl")
        source_error = source.get("error")
        source_records = payload_records_by_source.get(source_key, [])
        source_record_ids = {str(item.get("id")) for item in source_records if item.get("id")}
        source_record_urls = {str(item.get("obituaryUrl")) for item in source_records if item.get("obituaryUrl")}

        previous_latest_obit = latest_obit_by_source.get(source_key)
        previous_checkpoint_id = None
        previous_checkpoint_url = None
        previous_latest_source = latest_source_by_key.get(source_key)
        if previous_latest_source:
            previous_checkpoint_id = previous_latest_source.get("last_new_obituary_id") or None
            previous_checkpoint_url = previous_latest_source.get("last_new_obituary_url") or None

        if not previous_checkpoint_id and previous_latest_obit:
            previous_checkpoint_id = previous_latest_obit.get("id")
            previous_checkpoint_url = previous_latest_obit.get("obituary_url")

        last_known_found: bool | None
        if not previous_checkpoint_id and not previous_checkpoint_url:
            last_known_found = None
        else:
            last_known_found = bool(
                (previous_checkpoint_id and previous_checkpoint_id in source_record_ids)
                or (previous_checkpoint_url and previous_checkpoint_url in source_record_urls)
            )

        existing_ids = existing_ids_by_source.get(source_key, set())
        new_record_candidates = [item for item in source_records if str(item.get("id") or "") not in existing_ids]
        has_new_obituaries = len(new_record_candidates) > 0

        previous_no_new_runs = 0
        if previous_latest_source and previous_latest_source.get("consecutive_no_new_runs") is not None:
            try:
                previous_no_new_runs = int(previous_latest_source.get("consecutive_no_new_runs") or 0)
            except Exception:
                previous_no_new_runs = 0
        consecutive_no_new_runs = 0 if has_new_obituaries else previous_no_new_runs + 1

        freshness, needs_reprogramming, freshness_reason = _compute_source_freshness(
            source_status=source_status,
            has_new_obituaries=has_new_obituaries,
            last_known_found=last_known_found,
            consecutive_no_new_runs=consecutive_no_new_runs,
            no_new_runs_red_threshold=no_new_runs_red_threshold,
            source_error=str(source_error or ""),
        )

        current_checkpoint_id = previous_checkpoint_id
        current_checkpoint_url = previous_checkpoint_url
        current_checkpoint_at = None
        if previous_latest_source:
            current_checkpoint_at = previous_latest_source.get("last_new_obituary_at")

        if has_new_obituaries:
            newest_record = new_record_candidates[0]
            current_checkpoint_id = str(newest_record.get("id") or current_checkpoint_id or "") or None
            current_checkpoint_url = str(newest_record.get("obituaryUrl") or current_checkpoint_url or "") or None
            current_checkpoint_at = _as_iso(newest_record.get("scrapedAt")) or timestamp
        elif not current_checkpoint_id and source_records:
            fallback_record = source_records[0]
            current_checkpoint_id = str(fallback_record.get("id") or "") or None
            current_checkpoint_url = str(fallback_record.get("obituaryUrl") or "") or None
            current_checkpoint_at = _as_iso(fallback_record.get("scrapedAt")) or timestamp

        conn.execute(
            """
            INSERT INTO scrape_source_status (
                run_id, source_key, source_name, status, freshness_status,
                freshness_reason, has_new_obituaries, last_known_found, needs_reprogramming,
                listing_url, pages_discovered, obituaries_scraped,
                duration_ms, error, last_known_obituary_id,
                last_known_obituary_url, checked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                source_key,
                source_name,
                source_status,
                freshness,
                freshness_reason,
                1 if has_new_obituaries else 0,
                _as_bool_int(last_known_found),
                1 if needs_reprogramming else 0,
                listing_url,
                pages_discovered,
                obits_scraped,
                duration_ms,
                source_error,
                previous_checkpoint_id,
                previous_checkpoint_url,
                timestamp,
            ),
        )

        conn.execute(
            """
            INSERT INTO scrape_source_latest (
                source_key, source_name, status, freshness_status, listing_url,
                freshness_reason, has_new_obituaries, last_known_found, needs_reprogramming,
                consecutive_no_new_runs, last_new_obituary_id, last_new_obituary_url, last_new_obituary_at,
                obituaries_scraped, duration_ms, error, run_id, checked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_key) DO UPDATE SET
                source_name = excluded.source_name,
                status = excluded.status,
                freshness_status = excluded.freshness_status,
                freshness_reason = excluded.freshness_reason,
                has_new_obituaries = excluded.has_new_obituaries,
                last_known_found = excluded.last_known_found,
                needs_reprogramming = excluded.needs_reprogramming,
                consecutive_no_new_runs = excluded.consecutive_no_new_runs,
                last_new_obituary_id = excluded.last_new_obituary_id,
                last_new_obituary_url = excluded.last_new_obituary_url,
                last_new_obituary_at = excluded.last_new_obituary_at,
                listing_url = excluded.listing_url,
                obituaries_scraped = excluded.obituaries_scraped,
                duration_ms = excluded.duration_ms,
                error = excluded.error,
                run_id = excluded.run_id,
                checked_at = excluded.checked_at
            """,
            (
                source_key,
                source_name,
                source_status,
                freshness,
                listing_url,
                freshness_reason,
                1 if has_new_obituaries else 0,
                _as_bool_int(last_known_found),
                1 if needs_reprogramming else 0,
                consecutive_no_new_runs,
                current_checkpoint_id,
                current_checkpoint_url,
                current_checkpoint_at,
                obits_scraped,
                duration_ms,
                source_error,
                run_id,
                timestamp,
            ),
        )

    conn.commit()

    return {
        "runId": run_id,
        "obituariesUpserted": upserted_obituaries,
        "queueRecordsSeeded": seeded_queue_records,
        "sourcesTracked": len(sources),
        "status": run_status,
    }


def ingest_selected_output_file(
    output_path: Path | None = None,
    db_path: Path | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> dict[str, Any]:
    source_path = output_path or SELECTED_OUTPUT_PATH
    if not source_path.exists():
        raise FileNotFoundError(f"Selected output file not found: {source_path}")

    payload = json.loads(source_path.read_text(encoding="utf-8"))
    with get_connection(db_path=db_path) as conn:
        return ingest_selected_output(
            conn,
            payload,
            started_at=started_at,
            finished_at=finished_at,
        )


def fetch_feed(conn: sqlite3.Connection, limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
    ensure_schema(conn)

    where_clause = ""
    params: list[Any] = []
    if status:
        where_clause = "WHERE q.status = ?"
        params.append(status)

    params.append(max(1, int(limit)))

    rows = conn.execute(
        f"""
        SELECT
            o.id,
            o.source_key,
            o.source_name,
            o.listing_url,
            o.obituary_url,
            o.name,
            o.birth_date,
            o.death_date,
            o.age,
            o.summary,
            o.photo_url,
            o.scraped_at,
                        COALESCE(NULLIF(TRIM(q.override_name), ''), o.name) AS effective_name,
                        COALESCE(NULLIF(TRIM(q.override_birth_date), ''), o.birth_date) AS effective_birth_date,
                        COALESCE(NULLIF(TRIM(q.override_death_date), ''), o.death_date) AS effective_death_date,
            q.status AS queue_status,
            q.scheduled_for,
            q.posted_at,
            q.archived_at,
            q.facebook_post_id,
            q.comment_url,
            q.last_error,
            q.retry_count,
            q.retry_at,
                        q.override_name,
                        q.override_birth_date,
                        q.override_death_date,
                        q.override_reason,
                        q.override_updated_at,
                        q.override_updated_by,
                        CASE
                                WHEN NULLIF(TRIM(COALESCE(q.override_name, '')), '') IS NOT NULL
                                    OR NULLIF(TRIM(COALESCE(q.override_birth_date, '')), '') IS NOT NULL
                                    OR NULLIF(TRIM(COALESCE(q.override_death_date, '')), '') IS NOT NULL
                                THEN 1
                                ELSE 0
                        END AS has_overrides,
            q.updated_at AS queue_updated_at
        FROM obituaries o
        LEFT JOIN post_queue q ON q.obituary_id = o.id
        {where_clause}
        ORDER BY COALESCE(o.scraped_at, o.updated_at) DESC
        LIMIT ?
        """,
        params,
    ).fetchall()

    return [_sanitize_feed_row_names(dict(row)) for row in rows]


def fetch_queue_item(conn: sqlite3.Connection, obituary_id: str) -> dict[str, Any] | None:
    ensure_schema(conn)

    normalized_id = str(obituary_id or "").strip()
    if not normalized_id:
        return None

    row = conn.execute(
        """
        SELECT
            o.id,
            o.source_key,
            o.source_name,
            o.listing_url,
            o.obituary_url,
            o.name,
            o.birth_date,
            o.death_date,
            o.age,
            o.summary,
            o.photo_url,
            o.scraped_at,
                        COALESCE(NULLIF(TRIM(q.override_name), ''), o.name) AS effective_name,
                        COALESCE(NULLIF(TRIM(q.override_birth_date), ''), o.birth_date) AS effective_birth_date,
                        COALESCE(NULLIF(TRIM(q.override_death_date), ''), o.death_date) AS effective_death_date,
            q.status AS queue_status,
            q.scheduled_for,
            q.posted_at,
            q.archived_at,
            q.facebook_post_id,
            q.comment_url,
            q.last_error,
            q.retry_count,
            q.retry_at,
                        q.override_name,
                        q.override_birth_date,
                        q.override_death_date,
                        q.override_reason,
                        q.override_updated_at,
                        q.override_updated_by,
                        CASE
                                WHEN NULLIF(TRIM(COALESCE(q.override_name, '')), '') IS NOT NULL
                                    OR NULLIF(TRIM(COALESCE(q.override_birth_date, '')), '') IS NOT NULL
                                    OR NULLIF(TRIM(COALESCE(q.override_death_date, '')), '') IS NOT NULL
                                THEN 1
                                ELSE 0
                        END AS has_overrides,
            q.updated_at AS queue_updated_at
        FROM obituaries o
        LEFT JOIN post_queue q ON q.obituary_id = o.id
        WHERE o.id = ?
        LIMIT 1
        """,
        (normalized_id,),
    ).fetchone()

    if not row:
        return None
    return _sanitize_feed_row_names(dict(row))


def fetch_queue_override_record(conn: sqlite3.Connection, obituary_id: str) -> dict[str, Any] | None:
    item = fetch_queue_item(conn, obituary_id=obituary_id)
    if not item:
        return None

    return {
        "obituary_id": item.get("id"),
        "queue_status": item.get("queue_status"),
        "source_name": item.get("source_name"),
        "obituary_url": item.get("obituary_url"),
        "name": item.get("name"),
        "birth_date": item.get("birth_date"),
        "death_date": item.get("death_date"),
        "effective_name": item.get("effective_name") or item.get("name"),
        "effective_birth_date": item.get("effective_birth_date") or item.get("birth_date"),
        "effective_death_date": item.get("effective_death_date") or item.get("death_date"),
        "override_name": item.get("override_name"),
        "override_birth_date": item.get("override_birth_date"),
        "override_death_date": item.get("override_death_date"),
        "override_reason": item.get("override_reason"),
        "override_updated_at": item.get("override_updated_at"),
        "override_updated_by": item.get("override_updated_by"),
        "has_overrides": bool(item.get("has_overrides")),
    }


def update_queue_overrides(
    conn: sqlite3.Connection,
    obituary_id: str,
    *,
    override_name: Any = None,
    override_birth_date: Any = None,
    override_death_date: Any = None,
    override_reason: Any = None,
    initiated_by: str | None = None,
) -> dict[str, Any]:
    ensure_schema(conn)

    normalized_id = str(obituary_id or "").strip()
    if not normalized_id:
        raise ValueError("obituaryId is required.")

    item = fetch_queue_item(conn, obituary_id=normalized_id)
    if not item:
        raise ValueError(f"Obituary not found for ID: {normalized_id}")

    queue_status = str(item.get("queue_status") or "").strip().lower()
    if queue_status != "staged":
        raise ValueError("Overrides can only be edited while the record is in staged status.")

    normalized_name = _clean_person_name(
        _normalize_override_text(override_name),
        source_name=item.get("source_name"),
    )
    normalized_birth = _normalize_override_text(override_birth_date)
    normalized_death = _normalize_override_text(override_death_date)
    normalized_reason = _normalize_override_text(override_reason)

    if not (normalized_name or normalized_birth or normalized_death):
        normalized_reason = None

    timestamp = now_iso()
    actor = str(initiated_by or "").strip() or "ui_override"

    conn.execute(
        """
        UPDATE post_queue
        SET
            override_name = ?,
            override_birth_date = ?,
            override_death_date = ?,
            override_reason = ?,
            override_updated_at = ?,
            override_updated_by = ?,
            updated_at = ?
        WHERE obituary_id = ?
        """,
        (
            normalized_name,
            normalized_birth,
            normalized_death,
            normalized_reason,
            timestamp,
            actor,
            timestamp,
            normalized_id,
        ),
    )

    metadata = {
        "action": "override_update",
        "overrideName": normalized_name,
        "overrideBirthDate": normalized_birth,
        "overrideDeathDate": normalized_death,
        "overrideReason": normalized_reason,
    }
    metadata_json = json.dumps({k: v for k, v in metadata.items() if v is not None}, ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO queue_transition_audit (
            obituary_id,
            from_status,
            to_status,
            action_at,
            initiated_by,
            metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            normalized_id,
            queue_status,
            queue_status,
            timestamp,
            actor,
            metadata_json,
        ),
    )

    conn.commit()

    refreshed = fetch_queue_override_record(conn, obituary_id=normalized_id)
    if not refreshed:
        raise ValueError(f"Obituary not found for ID: {normalized_id}")
    return refreshed


def fetch_queue_counts(conn: sqlite3.Connection) -> dict[str, int]:
    ensure_schema(conn)
    counts = {status: 0 for status in QUEUE_STATUSES}
    rows = conn.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM post_queue
        GROUP BY status
        """
    ).fetchall()
    for row in rows:
        status = str(row[0] or "").strip().lower()
        if status not in counts:
            continue
        counts[status] = int(row[1] or 0)
    return counts


def transition_post_queue_status(
    conn: sqlite3.Connection,
    obituary_ids: list[str],
    to_status: str,
    scheduled_for: str | None = None,
    posted_at: str | None = None,
    archived_at: str | None = None,
    facebook_post_id: str | None = None,
    comment_url: str | None = None,
    last_error: str | None = None,
    retry_count: int | None = None,
    retry_at: str | None = None,
    metadata_extra: dict[str, Any] | None = None,
    initiated_by: str | None = None,
    allow_any_transition: bool = False,
) -> dict[str, Any]:
    ensure_schema(conn)

    normalized_ids: list[str] = []
    for obituary_id in obituary_ids:
        candidate = str(obituary_id or "").strip()
        if candidate:
            normalized_ids.append(candidate)

    unique_ids = list(dict.fromkeys(normalized_ids))
    if not unique_ids:
        raise ValueError("At least one obituary ID is required.")

    normalized_target = str(to_status or "").strip().lower()
    if normalized_target not in QUEUE_STATUSES:
        raise ValueError(f"Invalid target status: {to_status}")

    placeholders = ",".join(["?"] * len(unique_ids))
    rows = conn.execute(
        f"""
        SELECT obituary_id, status
        FROM post_queue
        WHERE obituary_id IN ({placeholders})
        """,
        unique_ids,
    ).fetchall()
    current_by_id = {str(row[0]): str(row[1] or "").strip().lower() for row in rows}

    missing_ids = [obituary_id for obituary_id in unique_ids if obituary_id not in current_by_id]
    if missing_ids:
        raise ValueError(f"Queue record not found for obituary IDs: {', '.join(missing_ids[:10])}")

    if not allow_any_transition:
        invalid_transitions: list[str] = []
        for obituary_id in unique_ids:
            from_status = current_by_id[obituary_id]
            allowed_targets = ALLOWED_QUEUE_TRANSITIONS.get(from_status, set())
            if normalized_target not in allowed_targets:
                invalid_transitions.append(f"{obituary_id} ({from_status} -> {normalized_target})")

        if invalid_transitions:
            details = "; ".join(invalid_transitions[:10])
            raise ValueError(f"Invalid queue transition(s): {details}")

    timestamp = now_iso()
    now_dt = datetime.now(timezone.utc)

    scheduled_value = _as_iso(scheduled_for)
    if normalized_target == "scheduled":
        if not scheduled_value:
            raise ValueError("scheduledFor is required when moving to scheduled status.")
        scheduled_dt = _parse_iso_datetime(scheduled_value)
        if scheduled_dt <= now_dt:
            raise ValueError("scheduledFor must be a future timestamp.")
        scheduled_value = scheduled_dt.isoformat()

    posted_value = _as_iso(posted_at) or timestamp
    archived_value = _as_iso(archived_at) or timestamp

    set_clauses = ["status = ?", "updated_at = ?"]
    params: list[Any] = [normalized_target, timestamp]

    if normalized_target == "new":
        set_clauses.extend(
            [
                "scheduled_for = NULL",
                "posted_at = NULL",
                "archived_at = NULL",
                "facebook_post_id = NULL",
                "comment_url = NULL",
                "last_error = NULL",
                "retry_count = 0",
                "retry_at = NULL",
            ]
        )
    elif normalized_target == "staged":
        set_clauses.extend(
            [
                "scheduled_for = NULL",
                "posted_at = NULL",
                "archived_at = NULL",
            ]
        )
    elif normalized_target == "scheduled":
        set_clauses.extend(["scheduled_for = ?", "posted_at = NULL", "archived_at = NULL", "retry_at = NULL"])
        params.append(scheduled_value)
    elif normalized_target == "posted":
        set_clauses.extend(["posted_at = ?", "archived_at = NULL", "last_error = NULL", "retry_count = 0", "retry_at = NULL"])
        params.append(posted_value)
    elif normalized_target == "archived":
        set_clauses.append("archived_at = ?")
        params.append(archived_value)

    if facebook_post_id is not None:
        set_clauses.append("facebook_post_id = ?")
        params.append(str(facebook_post_id).strip() or None)
    if comment_url is not None:
        set_clauses.append("comment_url = ?")
        params.append(str(comment_url).strip() or None)
    if last_error is not None:
        set_clauses.append("last_error = ?")
        params.append(str(last_error).strip() or None)
    if retry_count is not None:
        try:
            safe_retry_count = max(0, int(retry_count))
        except Exception:
            raise ValueError("retryCount must be an integer >= 0.")
        set_clauses.append("retry_count = ?")
        params.append(safe_retry_count)
    if retry_at is not None:
        set_clauses.append("retry_at = ?")
        params.append(str(retry_at).strip() or None)

    update_sql = f"""
        UPDATE post_queue
        SET {', '.join(set_clauses)}
        WHERE obituary_id IN ({placeholders})
    """
    conn.execute(update_sql, params + unique_ids)

    initiator = str(initiated_by or "").strip() or None
    transition_metadata = {
        "scheduledFor": scheduled_value,
        "postedAt": posted_value if normalized_target == "posted" else None,
        "archivedAt": archived_value if normalized_target == "archived" else None,
        "facebookPostId": str(facebook_post_id).strip() if facebook_post_id else None,
        "commentUrl": str(comment_url).strip() if comment_url else None,
        "lastError": str(last_error).strip() if last_error else None,
        "retryCount": max(0, int(retry_count)) if retry_count is not None else None,
        "retryAt": str(retry_at).strip() if retry_at else None,
    }
    if isinstance(metadata_extra, dict):
        for key, value in metadata_extra.items():
            if value is not None:
                transition_metadata[str(key)] = value
    metadata_json = json.dumps({k: v for k, v in transition_metadata.items() if v is not None}, ensure_ascii=False)

    for obituary_id in unique_ids:
        conn.execute(
            """
            INSERT INTO queue_transition_audit (
                obituary_id,
                from_status,
                to_status,
                action_at,
                initiated_by,
                metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                obituary_id,
                current_by_id[obituary_id],
                normalized_target,
                timestamp,
                initiator,
                metadata_json,
            ),
        )

    conn.commit()

    return {
        "ok": True,
        "toStatus": normalized_target,
        "updated": len(unique_ids),
        "obituaryIds": unique_ids,
        "updatedAt": timestamp,
        "auditRows": len(unique_ids),
    }


def archive_old_new_queue_records(
    conn: sqlite3.Connection,
    older_than_days: int,
    limit: int = 200,
    initiated_by: str | None = None,
) -> dict[str, Any]:
    ensure_schema(conn)

    days = max(1, int(older_than_days))
    max_items = max(1, min(int(limit), 1000))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows = conn.execute(
        """
        SELECT
            q.obituary_id,
            o.death_date,
            o.scraped_at
        FROM post_queue q
        INNER JOIN obituaries o ON o.id = q.obituary_id
        WHERE q.status = 'new'
        ORDER BY COALESCE(o.death_date, o.scraped_at, o.updated_at) ASC
        """
    ).fetchall()

    to_archive: list[str] = []
    for row in rows:
        obituary_id = str(row[0] or "").strip()
        if not obituary_id:
            continue
        reference_dt = _parse_flexible_datetime(row[1]) or _parse_flexible_datetime(row[2])
        if reference_dt is None:
            continue
        if reference_dt <= cutoff:
            to_archive.append(obituary_id)
        if len(to_archive) >= max_items:
            break

    if not to_archive:
        return {
            "ok": True,
            "olderThanDays": days,
            "cutoff": cutoff.isoformat(),
            "matched": 0,
            "archived": 0,
            "obituaryIds": [],
        }

    transition = transition_post_queue_status(
        conn,
        obituary_ids=to_archive,
        to_status="archived",
        archived_at=now_iso(),
        initiated_by=initiated_by or "archive_old_new",
        allow_any_transition=True,
    )

    return {
        "ok": True,
        "olderThanDays": days,
        "cutoff": cutoff.isoformat(),
        "matched": len(to_archive),
        "archived": int(transition.get("updated") or 0),
        "obituaryIds": to_archive,
        "transition": transition,
    }


def fetch_queue_transition_history(
    conn: sqlite3.Connection,
    obituary_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    ensure_schema(conn)

    normalized_limit = max(1, min(int(limit), 500))
    where_clause = ""
    params: list[Any] = []

    normalized_id = str(obituary_id or "").strip()
    if normalized_id:
        where_clause = "WHERE a.obituary_id = ?"
        params.append(normalized_id)

    params.append(normalized_limit)

    rows = conn.execute(
        f"""
        SELECT
            a.id,
            a.obituary_id,
            o.name,
            o.source_name,
            o.obituary_url,
            a.from_status,
            a.to_status,
            a.action_at,
            a.initiated_by,
            a.metadata_json
        FROM queue_transition_audit a
        LEFT JOIN obituaries o ON o.id = a.obituary_id
        {where_clause}
        ORDER BY a.id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()

    history: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        metadata_raw = item.get("metadata_json")
        parsed_metadata: dict[str, Any] | None = None
        if metadata_raw:
            try:
                maybe_obj = json.loads(str(metadata_raw))
                if isinstance(maybe_obj, dict):
                    parsed_metadata = maybe_obj
            except Exception:
                parsed_metadata = None
        item["metadata"] = parsed_metadata or {}
        history.append(item)

    return history


def fetch_source_latest(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_schema(conn)
    rows = conn.execute(
        """
        SELECT
            source_key,
            source_name,
            status,
            freshness_status,
            freshness_reason,
            has_new_obituaries,
            last_known_found,
            needs_reprogramming,
            consecutive_no_new_runs,
            last_new_obituary_id,
            last_new_obituary_url,
            last_new_obituary_at,
            listing_url,
            obituaries_scraped,
            duration_ms,
            error,
            run_id,
            checked_at
        FROM scrape_source_latest
        ORDER BY source_name ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_action_required_sources(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_schema(conn)
    rows = conn.execute(
        """
        SELECT
            source_key,
            source_name,
            status,
            freshness_status,
            freshness_reason,
            has_new_obituaries,
            last_known_found,
            needs_reprogramming,
            consecutive_no_new_runs,
            last_new_obituary_id,
            last_new_obituary_url,
            last_new_obituary_at,
            listing_url,
            obituaries_scraped,
            duration_ms,
            error,
            run_id,
            checked_at
        FROM scrape_source_latest
        WHERE needs_reprogramming = 1
                    AND NOT (
                        status = 'ok'
                        AND COALESCE(last_known_found, 0) = 1
                        AND COALESCE(has_new_obituaries, 0) = 0
                        AND COALESCE(error, '') = ''
                    )
        ORDER BY checked_at DESC, source_name ASC
        """
    ).fetchall()

    filtered: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        error_text = str(item.get("error") or "").strip().lower()
        transient_outage = bool(
            error_text
            and (
                "http error 530" in error_text
                or " 530 " in f" {error_text} "
                or "cloudflare" in error_text
                or "timed out" in error_text
                or "connection reset" in error_text
                or "temporary failure in name resolution" in error_text
                or "name or service not known" in error_text
            )
        )
        if transient_outage:
            continue
        filtered.append(item)

    return filtered
