#!/usr/bin/env python3
"""
Simple API server to serve obituary data for the website
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone, timedelta
import requests

import db_pipeline
import env_bootstrap

app = Flask(__name__)
CORS(app)  # Enable CORS for web requests
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_bootstrap.load_env_file()

SCRAPE_STATUS = {
    "state": "idle",
    "message": "No scrape started yet.",
    "startedAt": None,
    "finishedAt": None,
    "totalSources": 0,
    "completedSources": 0,
    "currentSourceKey": None,
    "currentSourceName": None,
    "safeMode": False,
    "skippedSources": 0,
    "totalObituaries": 0,
    "sources": [],
    "dbSync": None,
}
SCRAPE_LOCK = threading.Lock()
PUBLISH_STATUS = {
    "state": "idle",
    "message": "No publish run started yet.",
    "startedAt": None,
    "finishedAt": None,
    "processed": 0,
    "published": 0,
    "failed": 0,
    "lastError": None,
    "lastRun": None,
}
PUBLISH_LOCK = threading.Lock()
STATUS_DISPLAY_LABELS = {
    "new": "Recent",
    "staged": "Staged",
    "scheduled": "Scheduled",
    "posted": "Posted",
    "archived": "Archived",
}
WEBSITE_DATA_FILES = [
    "website_obituaries.json",
    "obituaries_for_website.json",
    "obituaries_gracegardens.json",
]


def _env_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    candidate = value.strip().lower()
    if candidate in {"1", "true", "yes", "on"}:
        return True
    if candidate in {"0", "false", "no", "off"}:
        return False
    return default


def _env_int(value: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(str(value or "").strip())
    except Exception:
        parsed = int(default)
    return max(minimum, min(parsed, maximum))


def _publish_worker_enabled() -> bool:
    return _env_bool(os.environ.get("PUBLISH_WORKER_ENABLED"), default=False)


def _publish_poll_seconds() -> int:
    return _env_int(os.environ.get("PUBLISH_POLL_SECONDS"), default=300, minimum=30, maximum=3600)


def _publish_provider() -> str:
    return str(os.environ.get("FB_PUBLISH_PROVIDER", "mock") or "mock").strip().lower()


def _facebook_graph_version() -> str:
    return str(os.environ.get("FB_GRAPH_API_VERSION", "v20.0") or "v20.0").strip() or "v20.0"


def _facebook_graph_base_url() -> str:
    configured = str(os.environ.get("FB_GRAPH_API_BASE_URL") or "").strip()
    if configured:
        return configured.rstrip("/")
    return f"https://graph.facebook.com/{_facebook_graph_version()}"


def _facebook_publish_timeout_seconds() -> int:
    return _env_int(os.environ.get("FB_PUBLISH_TIMEOUT_SECONDS"), default=20, minimum=5, maximum=120)


def _publish_retry_max_attempts() -> int:
    return _env_int(os.environ.get("PUBLISH_RETRY_MAX_ATTEMPTS"), default=3, minimum=1, maximum=20)


def _publish_retry_delay_seconds() -> int:
    return _env_int(os.environ.get("PUBLISH_RETRY_DELAY_SECONDS"), default=900, minimum=60, maximum=86400)


def _publish_worker_stale_multiplier() -> int:
    return _env_int(os.environ.get("PUBLISH_WORKER_STALE_MULTIPLIER"), default=3, minimum=2, maximum=20)


def _publish_worker_stale_min_seconds() -> int:
    return _env_int(os.environ.get("PUBLISH_WORKER_STALE_MIN_SECONDS"), default=600, minimum=120, maximum=86400)


def _publish_preflight_deep_interval_seconds() -> int:
    return _env_int(
        os.environ.get("PUBLISH_PREFLIGHT_DEEP_INTERVAL_SECONDS"),
        default=0,
        minimum=0,
        maximum=86400,
    )


def _facebook_sandbox_allow_comment_fallback() -> bool:
    return _env_bool(os.environ.get("FB_SANDBOX_ALLOW_COMMENT_FALLBACK"), default=False)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    candidate = str(value or "").strip()
    if not candidate:
        return None
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _secret_fingerprint(value: str | None) -> str | None:
    secret = str(value or "").strip()
    if not secret:
        return None
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    return digest[:12]


def _summarize_graph_error(response: requests.Response) -> str:
    body_text = (response.text or "").strip()
    fallback = body_text[:300] if body_text else f"HTTP {response.status_code}"

    try:
        parsed = response.json()
    except Exception:
        return fallback

    if not isinstance(parsed, dict):
        return fallback

    error = parsed.get("error")
    if isinstance(error, dict):
        message = str(error.get("message") or "").strip()
        code = error.get("code")
        if message and code is not None:
            return f"{message} (code {code})"
        if message:
            return message

    message = str(parsed.get("message") or "").strip()
    if message:
        return message

    return fallback


def _is_graph_permission_error(response: requests.Response) -> bool:
    try:
        parsed = response.json()
    except Exception:
        return False

    if not isinstance(parsed, dict):
        return False

    error = parsed.get("error")
    if not isinstance(error, dict):
        return False

    code = error.get("code")
    try:
        code_int = int(code)
    except Exception:
        code_int = None

    message = str(error.get("message") or "").strip().lower()
    if code_int == 200:
        return True
    if "do not have sufficient permissions" in message:
        return True
    if "insufficient permissions" in message:
        return True
    return False


def _build_facebook_comment_url(post_id: str, comment_id: str | None) -> str:
    normalized_post = str(post_id or "").strip()
    normalized_comment = str(comment_id or "").strip()
    if normalized_post and normalized_comment:
        return f"https://www.facebook.com/{normalized_post}?comment_id={normalized_comment}"
    if normalized_post:
        return f"https://www.facebook.com/{normalized_post}"
    if normalized_comment:
        return f"https://www.facebook.com/{normalized_comment}"
    return ""


def _delete_facebook_object(
    *,
    base_url: str,
    object_id: str,
    access_token: str,
    timeout_seconds: int,
) -> tuple[bool, str]:
    normalized_id = str(object_id or "").strip()
    if not normalized_id:
        return False, "Missing object ID for cleanup."

    try:
        response = requests.delete(
            f"{base_url}/{normalized_id}",
            params={"access_token": access_token},
            timeout=timeout_seconds,
        )
    except Exception as error:
        return False, f"Cleanup request failed: {error}"

    if response.status_code >= 400:
        return False, _summarize_graph_error(response)

    try:
        payload = response.json()
    except Exception:
        return True, ""

    if isinstance(payload, dict):
        success = payload.get("success")
        if isinstance(success, bool) and not success:
            return False, str(payload)[:300]

    return True, ""


def _append_preflight_check(
    checks: list[dict],
    *,
    name: str,
    ok: bool,
    detail: str,
    severity: str = "error",
    metadata: dict | None = None,
) -> None:
    item = {
        "name": name,
        "ok": bool(ok),
        "severity": "warning" if severity == "warning" else "error",
        "detail": str(detail or "").strip(),
    }
    if metadata:
        item["metadata"] = metadata
    checks.append(item)


def load_publish_preflight(deep: bool = False) -> tuple[dict, int]:
    provider = _publish_provider()
    strict_mode = not _facebook_sandbox_allow_comment_fallback()
    checks: list[dict] = []

    if provider == "mock":
        _append_preflight_check(
            checks,
            name="providerMode",
            ok=True,
            detail="Provider is mock. Graph preflight checks are skipped.",
            severity="warning",
        )
    elif provider != "facebook_sandbox":
        _append_preflight_check(
            checks,
            name="providerMode",
            ok=False,
            detail=f"Unsupported provider '{provider}'. Supported values: mock, facebook_sandbox.",
        )

    page_id = str(os.environ.get("FB_PAGE_ID") or "").strip()
    access_token = str(os.environ.get("FB_PAGE_ACCESS_TOKEN") or "").strip()
    base_url = _facebook_graph_base_url()
    timeout_seconds = _facebook_publish_timeout_seconds()

    if provider == "facebook_sandbox":
        _append_preflight_check(
            checks,
            name="envPageId",
            ok=bool(page_id),
            detail="FB_PAGE_ID is configured." if page_id else "FB_PAGE_ID is missing.",
        )
        _append_preflight_check(
            checks,
            name="envAccessToken",
            ok=bool(access_token),
            detail="FB_PAGE_ACCESS_TOKEN is configured." if access_token else "FB_PAGE_ACCESS_TOKEN is missing.",
        )

        if page_id and access_token:
            try:
                page_response = requests.get(
                    f"{base_url}/{page_id}",
                    params={"fields": "id,name", "access_token": access_token},
                    timeout=timeout_seconds,
                )
                if page_response.status_code >= 400:
                    _append_preflight_check(
                        checks,
                        name="pageLookup",
                        ok=False,
                        detail=f"Facebook page lookup failed: {_summarize_graph_error(page_response)}",
                    )
                else:
                    parsed_page = page_response.json() if page_response.content else {}
                    page_name = ""
                    if isinstance(parsed_page, dict):
                        page_name = str(parsed_page.get("name") or "").strip()
                    _append_preflight_check(
                        checks,
                        name="pageLookup",
                        ok=True,
                        detail="Facebook page lookup succeeded.",
                        metadata={"pageId": page_id, "pageName": page_name or None},
                    )
            except Exception as error:
                _append_preflight_check(
                    checks,
                    name="pageLookup",
                    ok=False,
                    detail=f"Facebook page lookup failed: {error}",
                )

            try:
                accounts_response = requests.get(
                    f"{base_url}/me/accounts",
                    params={"fields": "id,name,tasks", "access_token": access_token},
                    timeout=timeout_seconds,
                )
                if accounts_response.status_code >= 400:
                    _append_preflight_check(
                        checks,
                        name="pageMembership",
                        ok=True,
                        severity="warning",
                        detail=(
                            "Unable to verify page membership via /me/accounts. "
                            f"Continuing: {_summarize_graph_error(accounts_response)}"
                        ),
                    )
                else:
                    payload = accounts_response.json() if accounts_response.content else {}
                    rows = payload.get("data") if isinstance(payload, dict) else []
                    if not isinstance(rows, list):
                        rows = []

                    match = None
                    for row in rows:
                        if str((row or {}).get("id") or "").strip() == page_id:
                            match = row
                            break

                    if match is None:
                        _append_preflight_check(
                            checks,
                            name="pageMembership",
                            ok=True,
                            severity="warning",
                            detail="Configured page was not found in /me/accounts for this token.",
                        )
                    else:
                        tasks = match.get("tasks") if isinstance(match, dict) else []
                        if not isinstance(tasks, list):
                            tasks = []
                        normalized_tasks = {str(task or "").strip().upper() for task in tasks}
                        has_create = "CREATE_CONTENT" in normalized_tasks
                        if has_create:
                            _append_preflight_check(
                                checks,
                                name="pageMembership",
                                ok=True,
                                detail="Token can create content for the configured page.",
                                metadata={"tasks": sorted(normalized_tasks)},
                            )
                        else:
                            _append_preflight_check(
                                checks,
                                name="pageMembership",
                                ok=True,
                                severity="warning",
                                detail="Token did not report CREATE_CONTENT task for the configured page.",
                                metadata={"tasks": sorted(normalized_tasks)},
                            )
            except Exception as error:
                _append_preflight_check(
                    checks,
                    name="pageMembership",
                    ok=True,
                    severity="warning",
                    detail=f"Unable to verify page membership via /me/accounts: {error}",
                )

            if deep:
                probe_post_id = ""
                probe_comment_id = ""
                probe_post_ok = False
                try:
                    probe_message = f"[preflight] obituary publish probe {datetime.now(timezone.utc).isoformat()}"
                    probe_post_response = requests.post(
                        f"{base_url}/{page_id}/feed",
                        data={
                            "message": probe_message,
                            "published": "false",
                            "access_token": access_token,
                        },
                        timeout=timeout_seconds,
                    )
                    if probe_post_response.status_code >= 400:
                        _append_preflight_check(
                            checks,
                            name="deepPostCreate",
                            ok=False,
                            detail=(
                                "Failed to create unpublished deep-probe post: "
                                f"{_summarize_graph_error(probe_post_response)}"
                            ),
                        )
                    else:
                        parsed_probe = probe_post_response.json() if probe_post_response.content else {}
                        probe_post_id = str((parsed_probe or {}).get("id") or "").strip()
                        if not probe_post_id:
                            _append_preflight_check(
                                checks,
                                name="deepPostCreate",
                                ok=False,
                                detail="Deep-probe post create succeeded but no post ID was returned.",
                            )
                        else:
                            probe_post_ok = True
                            _append_preflight_check(
                                checks,
                                name="deepPostCreate",
                                ok=True,
                                detail="Deep-probe unpublished post create succeeded.",
                            )

                            probe_comment_response = requests.post(
                                f"{base_url}/{probe_post_id}/comments",
                                data={
                                    "message": "[preflight] obituary-link comment probe",
                                    "access_token": access_token,
                                },
                                timeout=timeout_seconds,
                            )
                            if probe_comment_response.status_code >= 400:
                                severity = "error" if strict_mode else "warning"
                                _append_preflight_check(
                                    checks,
                                    name="deepCommentCreate",
                                    ok=False,
                                    severity=severity,
                                    detail=(
                                        "Failed to create deep-probe comment: "
                                        f"{_summarize_graph_error(probe_comment_response)}"
                                    ),
                                )
                            else:
                                parsed_comment = (
                                    probe_comment_response.json() if probe_comment_response.content else {}
                                )
                                probe_comment_id = str((parsed_comment or {}).get("id") or "").strip()
                                if not probe_comment_id:
                                    severity = "error" if strict_mode else "warning"
                                    _append_preflight_check(
                                        checks,
                                        name="deepCommentCreate",
                                        ok=False,
                                        severity=severity,
                                        detail="Deep-probe comment create succeeded but no comment ID was returned.",
                                    )
                                else:
                                    _append_preflight_check(
                                        checks,
                                        name="deepCommentCreate",
                                        ok=True,
                                        detail="Deep-probe comment create succeeded.",
                                    )
                except Exception as error:
                    _append_preflight_check(
                        checks,
                        name="deepPostCreate",
                        ok=False,
                        detail=f"Deep-probe publish checks failed: {error}",
                    )
                finally:
                    if probe_comment_id:
                        cleanup_ok, cleanup_error = _delete_facebook_object(
                            base_url=base_url,
                            object_id=probe_comment_id,
                            access_token=access_token,
                            timeout_seconds=timeout_seconds,
                        )
                        _append_preflight_check(
                            checks,
                            name="deepCommentCleanup",
                            ok=cleanup_ok,
                            severity="warning",
                            detail=(
                                "Deep-probe comment cleanup succeeded."
                                if cleanup_ok
                                else f"Deep-probe comment cleanup failed: {cleanup_error}"
                            ),
                        )

                    if probe_post_id and probe_post_ok:
                        cleanup_ok, cleanup_error = _delete_facebook_object(
                            base_url=base_url,
                            object_id=probe_post_id,
                            access_token=access_token,
                            timeout_seconds=timeout_seconds,
                        )
                        _append_preflight_check(
                            checks,
                            name="deepPostCleanup",
                            ok=cleanup_ok,
                            severity="warning",
                            detail=(
                                "Deep-probe post cleanup succeeded."
                                if cleanup_ok
                                else f"Deep-probe post cleanup failed: {cleanup_error}"
                            ),
                        )

    failed_count = sum(1 for item in checks if (not item.get("ok")) and item.get("severity") != "warning")
    warning_count = sum(1 for item in checks if (not item.get("ok")) and item.get("severity") == "warning")
    passed_count = sum(1 for item in checks if item.get("ok"))

    payload = {
        "ok": failed_count == 0,
        "provider": provider,
        "strictMode": strict_mode,
        "deepProbeRequested": bool(deep),
        "checks": checks,
        "summary": {
            "passed": passed_count,
            "failed": failed_count,
            "warnings": warning_count,
        },
        "dbPath": str(db_pipeline.get_db_path()),
    }

    if failed_count:
        payload["error"] = (
            f"Publish preflight failed with {failed_count} blocking check(s). "
            "Resolve failed checks before running publish."
        )

    return payload, 200


def run_publish_preflight(
    *,
    deep: bool = False,
    initiated_by: str = "api_publish_preflight",
) -> tuple[dict, int]:
    body, status_code = load_publish_preflight(deep=deep)

    try:
        with db_pipeline.get_connection() as conn:
            recorded = db_pipeline.record_publish_preflight_run(
                conn,
                body=body,
                status_code=status_code,
                initiated_by=initiated_by,
            )
            latest = db_pipeline.get_latest_publish_preflight_run(conn)
    except Exception:
        recorded = None
        latest = None

    if recorded:
        body["recordedRun"] = recorded
    if latest:
        body["latestRun"] = latest

    return body, status_code


def _load_latest_publish_preflight_run() -> dict | None:
    try:
        with db_pipeline.get_connection() as conn:
            return db_pipeline.get_latest_publish_preflight_run(conn)
    except Exception:
        return None


def _build_secret_lifecycle_status() -> dict:
    provider = _publish_provider()
    page_id = str(os.environ.get("FB_PAGE_ID") or "").strip()
    access_token = str(os.environ.get("FB_PAGE_ACCESS_TOKEN") or "").strip()

    required_env = {
        "FB_PUBLISH_PROVIDER": bool(provider),
        "FB_PAGE_ID": True if provider != "facebook_sandbox" else bool(page_id),
        "FB_PAGE_ACCESS_TOKEN": True if provider != "facebook_sandbox" else bool(access_token),
    }

    return {
        "provider": provider,
        "requiredEnv": required_env,
        "secretsPresent": {
            "FB_PAGE_ID": bool(page_id),
            "FB_PAGE_ACCESS_TOKEN": bool(access_token),
        },
        "fingerprints": {
            "FB_PAGE_ACCESS_TOKEN": _secret_fingerprint(access_token),
        },
    }


def _build_publish_operational_health(status: dict) -> dict:
    now_dt = datetime.now(timezone.utc)
    heartbeat_at = _parse_iso_datetime(status.get("heartbeatAt"))
    poll_seconds = max(30, int(status.get("pollSeconds") or _publish_poll_seconds()))
    stale_after_seconds = max(_publish_worker_stale_min_seconds(), poll_seconds * _publish_worker_stale_multiplier())
    worker_enabled = bool(status.get("workerEnabled"))

    heartbeat_age_seconds = None
    worker_stale = False
    alerts: list[dict] = []
    if heartbeat_at is not None:
        heartbeat_age_seconds = max(0, int((now_dt - heartbeat_at).total_seconds()))
        if worker_enabled and heartbeat_age_seconds > stale_after_seconds:
            worker_stale = True
            alerts.append(
                {
                    "severity": "error",
                    "kind": "worker_heartbeat",
                    "message": (
                        "Publish worker heartbeat is stale "
                        f"({heartbeat_age_seconds}s old, threshold {stale_after_seconds}s)."
                    ),
                }
            )
    elif worker_enabled:
        worker_stale = True
        alerts.append(
            {
                "severity": "error",
                "kind": "worker_heartbeat",
                "message": "Publish worker is enabled but has not reported a heartbeat yet.",
            }
        )

    latest_preflight = _load_latest_publish_preflight_run()
    deep_interval_seconds = _publish_preflight_deep_interval_seconds()
    deep_preflight_age_seconds = None
    deep_preflight_stale = False

    if latest_preflight:
        run_at = _parse_iso_datetime(latest_preflight.get("runAt"))
        if run_at is not None:
            deep_preflight_age_seconds = max(0, int((now_dt - run_at).total_seconds()))
        if not bool(latest_preflight.get("ok")):
            alerts.append(
                {
                    "severity": "error",
                    "kind": "deep_preflight",
                    "message": (
                        "Latest publish preflight has blocking failures: "
                        + ", ".join(latest_preflight.get("failedChecks") or [])
                    ).rstrip(", "),
                }
            )
    elif deep_interval_seconds > 0:
        deep_preflight_stale = True
        alerts.append(
            {
                "severity": "error",
                "kind": "deep_preflight",
                "message": "No recorded publish preflight run found.",
            }
        )

    if deep_interval_seconds > 0:
        deep_stale_after = max(600, deep_interval_seconds * 2)
        if deep_preflight_age_seconds is not None and deep_preflight_age_seconds > deep_stale_after:
            deep_preflight_stale = True
            alerts.append(
                {
                    "severity": "warning",
                    "kind": "deep_preflight_schedule",
                    "message": (
                        "Deep preflight checks appear overdue "
                        f"({deep_preflight_age_seconds}s old, threshold {deep_stale_after}s)."
                    ),
                }
            )

    status["heartbeatAgeSeconds"] = heartbeat_age_seconds
    status["workerStaleAfterSeconds"] = stale_after_seconds
    status["workerStale"] = worker_stale
    status["deepPreflightIntervalSeconds"] = deep_interval_seconds
    status["deepPreflightAgeSeconds"] = deep_preflight_age_seconds
    status["deepPreflightStale"] = deep_preflight_stale

    secret_status = _build_secret_lifecycle_status()
    secret_missing = [key for key, present in secret_status.get("requiredEnv", {}).items() if not bool(present)]
    if secret_missing:
        alerts.append(
            {
                "severity": "error",
                "kind": "secret_lifecycle",
                "message": "Missing required secret configuration: " + ", ".join(secret_missing),
            }
        )

    return {
        "ok": not any(item.get("severity") == "error" for item in alerts),
        "timestamp": now_iso(),
        "publishStatus": status,
        "latestPreflight": latest_preflight,
        "secretLifecycle": secret_status,
        "alerts": alerts,
        "dbPath": str(db_pipeline.get_db_path()),
    }


def _extract_publish_warning_record(result: dict) -> dict | None:
    if not isinstance(result, dict):
        return None

    publish_payload = result.get("publish")
    if not isinstance(publish_payload, dict):
        return None

    provider_response = publish_payload.get("providerResponse")
    if not isinstance(provider_response, dict):
        return None

    fallback_applied = bool(provider_response.get("comment_fallback_applied"))
    warning_text = str(provider_response.get("comment_warning") or "").strip()
    if not fallback_applied and not warning_text:
        return None

    return {
        "obituaryId": result.get("obituaryId"),
        "provider": publish_payload.get("provider") or result.get("provider"),
        "commentFallbackApplied": fallback_applied,
        "warning": warning_text or "First comment was not posted due to permissions.",
    }


def _collect_publish_warnings(results: list[dict]) -> list[dict]:
    warnings: list[dict] = []
    for item in results:
        warning = _extract_publish_warning_record(item)
        if warning:
            warnings.append(warning)
    return warnings


POST_PREVIEW_SETTINGS = {
    "pageName": os.environ.get("FACEBOOK_PAGE_NAME", "McLennan County Obits - Obituaries"),
    "namePrefix": os.environ.get("FB_PREVIEW_NAME_PREFIX", ""),
    "dateSeparator": os.environ.get("FB_PREVIEW_DATE_SEPARATOR", " - "),
    "dateFormat": os.environ.get("FB_PREVIEW_DATE_FORMAT", "%B %d, %Y"),
    "unknownDateLabel": os.environ.get("FB_PREVIEW_UNKNOWN_DATE", "Unknown"),
    "includeDoveEmoji": _env_bool(os.environ.get("FB_PREVIEW_INCLUDE_DOVE"), default=False),
    "firstCommentPrefix": os.environ.get("FB_PREVIEW_COMMENT_PREFIX", ""),
}
POST_PREVIEW_ALLOWED_DATE_FORMATS = {
    "%B %d, %Y",
    "%b %d, %Y",
    "%Y-%m-%d",
    "%m/%d/%Y",
}


def _coerce_preview_settings_updates(payload: dict) -> tuple[dict, list[str]]:
    updates: dict = {}
    errors: list[str] = []

    string_keys = {
        "pageName",
        "namePrefix",
        "dateSeparator",
        "dateFormat",
        "unknownDateLabel",
        "firstCommentPrefix",
    }
    for key in string_keys:
        if key not in payload:
            continue
        value = str(payload.get(key) or "")
        if key == "dateFormat" and value and value not in POST_PREVIEW_ALLOWED_DATE_FORMATS:
            errors.append(
                f"dateFormat must be one of: {', '.join(sorted(POST_PREVIEW_ALLOWED_DATE_FORMATS))}"
            )
            continue
        updates[key] = value

    if "includeDoveEmoji" in payload:
        updates["includeDoveEmoji"] = bool(payload.get("includeDoveEmoji"))

    return updates, errors


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_scrape_status(updates: dict) -> None:
    with SCRAPE_LOCK:
        SCRAPE_STATUS.update(updates)


def _build_initial_source_status(sources: dict[str, dict]) -> list[dict]:
    items: list[dict] = []
    for source_key, config in sources.items():
        items.append(
            {
                "sourceKey": source_key,
                "sourceName": config.get("name", source_key),
                "status": "pending",
                "obituariesScraped": 0,
                "durationMs": 0,
                "error": None,
            }
        )
    return items


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_falsy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"0", "false", "no", "off"}


def is_railway_environment() -> bool:
    return bool(os.environ.get("RAILWAY_PROJECT_ID") or os.environ.get("RAILWAY_ENVIRONMENT"))


def is_scraper_safe_mode_enabled() -> bool:
    configured = os.environ.get("SCRAPER_SAFE_MODE")
    if _is_truthy(configured):
        return True
    if _is_falsy(configured):
        return False
    return is_railway_environment()


def split_sources_for_safe_mode(all_sources: dict[str, dict], safe_mode: bool) -> tuple[dict[str, dict], list[dict], set[str]]:
    runnable_sources: dict[str, dict] = {}
    status_items: list[dict] = []
    skipped_keys: set[str] = set()

    for source_key, config in all_sources.items():
        source_name = config.get("name", source_key)
        scraper_type = str(config.get("scraper_type", "")).lower()
        if safe_mode and scraper_type == "selenium":
            skipped_keys.add(source_key)
            status_items.append(
                {
                    "sourceKey": source_key,
                    "sourceName": source_name,
                    "status": "skipped",
                    "obituariesScraped": 0,
                    "durationMs": 0,
                    "error": "Skipped in safe mode (selenium source).",
                }
            )
            continue

        runnable_sources[source_key] = config
        status_items.append(
            {
                "sourceKey": source_key,
                "sourceName": source_name,
                "status": "pending",
                "obituariesScraped": 0,
                "durationMs": 0,
                "error": None,
            }
        )

    return runnable_sources, status_items, skipped_keys


def load_previous_selected_records(selected_scraper) -> list:
    output_path = selected_scraper.OUTPUT_PATH
    if not output_path.exists():
        return []

    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    records: list = []
    for item in payload.get("obituaries", []):
        if not isinstance(item, dict):
            continue
        try:
            records.append(selected_scraper.ObituaryRecord(**item))
        except Exception:
            continue
    return records


def merge_records_with_previous(new_records: list, previous_records: list, refreshed_source_keys: set[str]) -> list:
    merged = list(new_records)
    for item in previous_records:
        source_key = getattr(item, "sourceKey", None)
        if source_key in refreshed_source_keys:
            continue
        merged.append(item)
    return merged


def read_json_file(path: str) -> dict | list | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def capture_current_website_snapshot() -> tuple[dict[str, str], dict[str, int]]:
    snapshot: dict[str, str] = {}
    summary = {"total_obituaries": 0, "working_funeral_homes": 0}

    for file_name in WEBSITE_DATA_FILES:
        file_path = os.path.join(BASE_DIR, file_name)
        if not os.path.exists(file_path):
            continue
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                content = handle.read()
            snapshot[file_name] = content
        except Exception:
            continue

    current = read_json_file(os.path.join(BASE_DIR, "website_obituaries.json"))
    if isinstance(current, dict):
        current_summary = current.get("summary", {})
        summary["total_obituaries"] = int(current_summary.get("total_obituaries", 0) or 0)
        summary["working_funeral_homes"] = int(current_summary.get("working_funeral_homes", 0) or 0)

    return snapshot, summary


def restore_website_snapshot(snapshot: dict[str, str]) -> None:
    for file_name, content in snapshot.items():
        file_path = os.path.join(BASE_DIR, file_name)
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(content)


def should_restore_previous_dataset(previous_summary: dict[str, int], current_summary: dict[str, int], safe_mode: bool) -> bool:
    if not safe_mode:
        return False

    previous_total = int(previous_summary.get("total_obituaries", 0) or 0)
    current_total = int(current_summary.get("total_obituaries", 0) or 0)
    previous_homes = int(previous_summary.get("working_funeral_homes", 0) or 0)
    current_homes = int(current_summary.get("working_funeral_homes", 0) or 0)

    return current_total < previous_total or current_homes < previous_homes


def run_scrape_job() -> None:
    try:
        import scrape_selected_obituaries as selected_scraper
        import bundle_for_website

        previous_snapshot, previous_summary = capture_current_website_snapshot()
        started_at = now_iso()

        all_sources = selected_scraper.load_selected_sources(include_inactive=False, source_keys=None)
        safe_mode = is_scraper_safe_mode_enabled()
        sources, source_status, skipped_keys = split_sources_for_safe_mode(all_sources, safe_mode=safe_mode)
        skipped_count = len(skipped_keys)
        started_message = "Preparing sources in safe mode..." if safe_mode else "Preparing sources..."
        _set_scrape_status(
            {
                "state": "running",
                "message": started_message,
                "startedAt": started_at,
                "finishedAt": None,
                "totalSources": len(source_status),
                "completedSources": skipped_count,
                "currentSourceKey": None,
                "currentSourceName": None,
                "safeMode": safe_mode,
                "skippedSources": skipped_count,
                "totalObituaries": 0,
                "sources": source_status,
                "dbSync": None,
            }
        )

        all_records: list = []
        all_results: list = []

        for index, (source_key, config) in enumerate(sources.items()):
            source_name = config.get("name", source_key)
            _set_scrape_status(
                {
                    "message": f"Scraping {source_name}...",
                    "currentSourceKey": source_key,
                    "currentSourceName": source_name,
                }
            )

            source_records, source_result = selected_scraper.scrape_source(
                source_key,
                config,
                max_obituaries=selected_scraper.MAX_OBITUARIES_PER_SOURCE,
            )
            source_records = selected_scraper.filter_records_to_lookback(
                source_records,
                lookback_days=selected_scraper.DEFAULT_LOOKBACK_DAYS,
            )
            source_result.obituariesScraped = len(source_records)
            if source_result.status == "ok" and not source_records:
                source_result.status = "no-data"

            all_records.extend(source_records)
            all_results.append(source_result)

            with SCRAPE_LOCK:
                for item in SCRAPE_STATUS["sources"]:
                    if item["sourceKey"] != source_key:
                        continue
                    item["status"] = source_result.status
                    item["obituariesScraped"] = source_result.obituariesScraped
                    item["durationMs"] = source_result.durationMs
                    item["error"] = source_result.error
                    break
                SCRAPE_STATUS["completedSources"] = skipped_count + index + 1
                SCRAPE_STATUS["totalObituaries"] = len(all_records)

        refreshed_keys = set(sources.keys())
        previous_records = load_previous_selected_records(selected_scraper)
        merged_records = merge_records_with_previous(all_records, previous_records, refreshed_source_keys=refreshed_keys)

        for source_key in skipped_keys:
            source_name = all_sources.get(source_key, {}).get("name", source_key)
            all_results.append(
                selected_scraper.SourceScrapeResult(
                    source=source_name,
                    sourceKey=source_key,
                    status="skipped",
                    listingUrl=str(all_sources.get(source_key, {}).get("obituaries_url", "")),
                    pagesDiscovered=0,
                    obituariesScraped=0,
                    durationMs=0,
                    error="Skipped in safe mode (selenium source).",
                )
            )

        selected_scraper.write_output(merged_records, all_results)
        bundle_for_website.create_unified_dataset()

        db_sync_result = db_pipeline.ingest_selected_output_file(
            output_path=selected_scraper.OUTPUT_PATH,
            started_at=started_at,
            finished_at=now_iso(),
        )

        latest_dataset = read_json_file(os.path.join(BASE_DIR, "website_obituaries.json"))
        latest_summary = {"total_obituaries": 0, "working_funeral_homes": 0}
        if isinstance(latest_dataset, dict):
            latest = latest_dataset.get("summary", {})
            latest_summary["total_obituaries"] = int(latest.get("total_obituaries", 0) or 0)
            latest_summary["working_funeral_homes"] = int(latest.get("working_funeral_homes", 0) or 0)

        guard_triggered = should_restore_previous_dataset(previous_summary, latest_summary, safe_mode=safe_mode)
        if guard_triggered:
            restore_website_snapshot(previous_snapshot)
            latest_summary = previous_summary

        mode_suffix = " (safe mode)" if safe_mode else ""
        guard_suffix = " with anti-regression restore" if guard_triggered else ""

        _set_scrape_status(
            {
                "state": "completed",
                "message": f"Scrape and bundle complete{mode_suffix}{guard_suffix}.",
                "finishedAt": now_iso(),
                "currentSourceKey": None,
                "currentSourceName": None,
                "totalObituaries": int(latest_summary.get("total_obituaries", len(merged_records)) or 0),
                "dbSync": db_sync_result,
            }
        )
    except Exception as error:
        _set_scrape_status(
            {
                "state": "error",
                "message": f"Scrape failed: {error}",
                "finishedAt": now_iso(),
                "currentSourceKey": None,
                "currentSourceName": None,
                "dbSync": None,
            }
        )


def load_db_feed(limit: int = 100, status: str | None = None) -> dict:
    try:
        with db_pipeline.get_connection() as conn:
            feed = db_pipeline.fetch_feed(conn, limit=limit, status=status)
        return {
            "ok": True,
            "count": len(feed),
            "statusFilter": status,
            "limit": limit,
            "dbPath": str(db_pipeline.get_db_path()),
            "obituaries": feed,
        }
    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
            "dbPath": str(db_pipeline.get_db_path()),
            "obituaries": [],
        }


def load_db_source_health() -> dict:
    try:
        with db_pipeline.get_connection() as conn:
            rows = db_pipeline.fetch_source_latest(conn)

        summary = {
            "green": sum(1 for row in rows if row.get("freshness_status") == "green"),
            "yellow": sum(1 for row in rows if row.get("freshness_status") == "yellow"),
            "red": sum(1 for row in rows if row.get("freshness_status") == "red"),
        }
        return {
            "ok": True,
            "count": len(rows),
            "dbPath": str(db_pipeline.get_db_path()),
            "summary": summary,
            "sources": rows,
        }
    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
            "dbPath": str(db_pipeline.get_db_path()),
            "sources": [],
        }


def load_db_action_required() -> dict:
    try:
        with db_pipeline.get_connection() as conn:
            rows = db_pipeline.fetch_action_required_sources(conn)

        return {
            "ok": True,
            "count": len(rows),
            "dbPath": str(db_pipeline.get_db_path()),
            "sources": rows,
        }
    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
            "dbPath": str(db_pipeline.get_db_path()),
            "sources": [],
        }


def _parse_limit_arg(default: int = 200, max_limit: int = 500) -> int:
    raw_limit = str(request.args.get("limit", "")).strip()
    if not raw_limit:
        return default
    try:
        parsed = int(raw_limit)
    except ValueError:
        return default
    return max(1, min(parsed, max_limit))


def _normalize_queue_status(value: str | None) -> str | None:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return None
    if candidate not in db_pipeline.QUEUE_STATUSES:
        return None
    return candidate


def _status_display_label(value: str | None) -> str | None:
    normalized = _normalize_queue_status(value)
    if not normalized:
        return None
    return STATUS_DISPLAY_LABELS.get(normalized, normalized.title())


def _format_obituary_date(value: str | None, *, date_format: str, unknown_label: str) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        return unknown_label

    attempts = [candidate]
    if candidate.endswith("Z"):
        attempts.append(candidate[:-1] + "+00:00")

    for item in attempts:
        try:
            parsed = datetime.fromisoformat(item)
            return parsed.strftime(date_format)
        except ValueError:
            continue

    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            parsed = datetime.strptime(candidate, fmt)
            return parsed.strftime(date_format)
        except ValueError:
            continue

    return candidate


def _build_post_preview(item: dict) -> dict:
    settings = POST_PREVIEW_SETTINGS
    name = str(item.get("effective_name") or item.get("name") or "Unknown").strip() or "Unknown"
    birth = _format_obituary_date(
        item.get("effective_birth_date") or item.get("birth_date"),
        date_format=str(settings["dateFormat"]),
        unknown_label=str(settings["unknownDateLabel"]),
    )
    death = _format_obituary_date(
        item.get("effective_death_date") or item.get("death_date"),
        date_format=str(settings["dateFormat"]),
        unknown_label=str(settings["unknownDateLabel"]),
    )

    name_prefix = str(settings.get("namePrefix") or "")
    include_dove = bool(settings.get("includeDoveEmoji"))
    emoji_prefix = "🕊️ " if include_dove else ""

    name_line = f"{emoji_prefix}{name_prefix}{name}".strip()
    date_line = f"{birth}{settings['dateSeparator']}{death}"
    post_text = f"{name_line}\n{date_line}"

    obituary_url = str(item.get("obituary_url") or "").strip()
    comment_prefix = str(settings.get("firstCommentPrefix") or "")
    first_comment_text = f"{comment_prefix}{obituary_url}" if obituary_url else ""

    return {
        "pageName": settings["pageName"],
        "postText": post_text,
        "name": name,
        "dateLine": date_line,
        "imageUrl": item.get("photo_url"),
        "sourceName": item.get("source_name"),
        "firstCommentText": first_comment_text,
        "firstCommentUrl": obituary_url,
        "usedOverrides": bool(item.get("has_overrides")),
        "templateSettings": dict(settings),
    }


def load_db_queue_override(obituary_id: str) -> tuple[dict, int]:
    try:
        with db_pipeline.get_connection() as conn:
            row = db_pipeline.fetch_queue_override_record(conn, obituary_id=obituary_id)

        if not row:
            return {
                "ok": False,
                "error": f"Obituary not found for ID: {obituary_id}",
                "dbPath": str(db_pipeline.get_db_path()),
            }, 404

        payload = {
            **row,
            "queue_status_display": _status_display_label(str(row.get("queue_status") or "")),
        }
        return {
            "ok": True,
            "dbPath": str(db_pipeline.get_db_path()),
            "override": payload,
        }, 200
    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
            "dbPath": str(db_pipeline.get_db_path()),
        }, 500


def save_db_queue_override(obituary_id: str, payload: dict) -> tuple[dict, int]:
    override_name = payload.get("overrideName", payload.get("name"))
    override_birth_date = payload.get("overrideBirthDate", payload.get("birthDate"))
    override_death_date = payload.get("overrideDeathDate", payload.get("deathDate"))
    override_reason = payload.get("overrideReason", payload.get("reason"))
    initiated_by = str(payload.get("initiatedBy") or "website_preview_override_save").strip() or "website_preview_override_save"

    try:
        with db_pipeline.get_connection() as conn:
            updated = db_pipeline.update_queue_overrides(
                conn,
                obituary_id=obituary_id,
                override_name=override_name,
                override_birth_date=override_birth_date,
                override_death_date=override_death_date,
                override_reason=override_reason,
                initiated_by=initiated_by,
            )
            counts = db_pipeline.fetch_queue_counts(conn)

        payload_row = {
            **updated,
            "queue_status_display": _status_display_label(str(updated.get("queue_status") or "")),
        }
        return {
            "ok": True,
            "dbPath": str(db_pipeline.get_db_path()),
            "counts": counts,
            "override": payload_row,
        }, 200
    except ValueError as error:
        return {
            "ok": False,
            "error": str(error),
            "dbPath": str(db_pipeline.get_db_path()),
        }, 400
    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
            "dbPath": str(db_pipeline.get_db_path()),
        }, 500


def load_db_post_preview(obituary_id: str) -> tuple[dict, int]:
    try:
        with db_pipeline.get_connection() as conn:
            item = db_pipeline.fetch_queue_item(conn, obituary_id=obituary_id)

        if not item:
            return {
                "ok": False,
                "error": f"Obituary not found for ID: {obituary_id}",
                "dbPath": str(db_pipeline.get_db_path()),
            }, 404

        preview_payload = _build_post_preview(item)

        return {
            "ok": True,
            "dbPath": str(db_pipeline.get_db_path()),
            "obituaryId": item.get("id"),
            "queueStatus": item.get("queue_status"),
            "settings": dict(POST_PREVIEW_SETTINGS),
            "preview": preview_payload,
        }, 200
    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
            "dbPath": str(db_pipeline.get_db_path()),
        }, 500


def load_db_feed_for_status(status: str, limit: int = 200) -> tuple[dict, int]:
    normalized = _normalize_queue_status(status)
    if not normalized:
        return {
            "ok": False,
            "error": f"Invalid queue status: {status}",
            "allowedStatuses": sorted(db_pipeline.QUEUE_STATUSES),
            "dbPath": str(db_pipeline.get_db_path()),
            "obituaries": [],
        }, 400

    payload = load_db_feed(limit=limit, status=normalized)
    if payload.get("ok") is not True:
        return payload, 500
    payload["statusDisplay"] = _status_display_label(normalized)
    return payload, 200


def load_db_queue_counts() -> tuple[dict, int]:
    try:
        with db_pipeline.get_connection() as conn:
            counts = db_pipeline.fetch_queue_counts(conn)
        return {
            "ok": True,
            "counts": counts,
            "dbPath": str(db_pipeline.get_db_path()),
        }, 200
    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
            "counts": {},
            "dbPath": str(db_pipeline.get_db_path()),
        }, 500


def load_db_queue_history(limit: int = 100, obituary_id: str | None = None) -> tuple[dict, int]:
    try:
        with db_pipeline.get_connection() as conn:
            rows = db_pipeline.fetch_queue_transition_history(
                conn,
                obituary_id=obituary_id,
                limit=limit,
            )
        for row in rows:
            row["from_status_display"] = _status_display_label(str(row.get("from_status") or ""))
            row["to_status_display"] = _status_display_label(str(row.get("to_status") or ""))
        return {
            "ok": True,
            "count": len(rows),
            "limit": limit,
            "obituaryId": obituary_id,
            "dbPath": str(db_pipeline.get_db_path()),
            "history": rows,
        }, 200
    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
            "count": 0,
            "limit": limit,
            "obituaryId": obituary_id,
            "dbPath": str(db_pipeline.get_db_path()),
            "history": [],
        }, 500


def transition_db_queue_records(payload: dict) -> tuple[dict, int]:
    obituary_ids: list[str] = []
    raw_ids = payload.get("obituaryIds")
    if isinstance(raw_ids, list):
        obituary_ids.extend(str(item or "").strip() for item in raw_ids)

    single_id = str(payload.get("obituaryId") or "").strip()
    if single_id:
        obituary_ids.append(single_id)

    target_status = str(payload.get("toStatus") or payload.get("status") or "").strip().lower()
    if not target_status:
        return {
            "ok": False,
            "error": "toStatus is required.",
            "dbPath": str(db_pipeline.get_db_path()),
        }, 400

    if not obituary_ids:
        return {
            "ok": False,
            "error": "At least one obituaryId is required.",
            "dbPath": str(db_pipeline.get_db_path()),
        }, 400

    try:
        with db_pipeline.get_connection() as conn:
            result = db_pipeline.transition_post_queue_status(
                conn,
                obituary_ids=obituary_ids,
                to_status=target_status,
                scheduled_for=payload.get("scheduledFor"),
                posted_at=payload.get("postedAt"),
                archived_at=payload.get("archivedAt"),
                facebook_post_id=payload.get("facebookPostId"),
                comment_url=payload.get("commentUrl"),
                last_error=payload.get("lastError"),
                retry_count=payload.get("retryCount"),
                retry_at=payload.get("retryAt"),
                initiated_by=payload.get("initiatedBy") or payload.get("actor") or "ui",
            )
            counts = db_pipeline.fetch_queue_counts(conn)

        return {
            **result,
            "counts": counts,
            "dbPath": str(db_pipeline.get_db_path()),
        }, 200
    except ValueError as error:
        return {
            "ok": False,
            "error": str(error),
            "dbPath": str(db_pipeline.get_db_path()),
        }, 400
    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
            "dbPath": str(db_pipeline.get_db_path()),
        }, 500


def archive_old_new_queue_records(payload: dict) -> tuple[dict, int]:
    raw_days = payload.get("olderThanDays", payload.get("days", 30))
    raw_limit = payload.get("limit", 200)
    initiated_by = str(payload.get("initiatedBy") or "website_preview_archive_old_new").strip() or "website_preview_archive_old_new"

    try:
        days = max(1, min(int(raw_days), 3650))
    except Exception:
        return {
            "ok": False,
            "error": "olderThanDays must be a positive integer.",
            "dbPath": str(db_pipeline.get_db_path()),
        }, 400

    try:
        limit = max(1, min(int(raw_limit), 1000))
    except Exception:
        return {
            "ok": False,
            "error": "limit must be a positive integer.",
            "dbPath": str(db_pipeline.get_db_path()),
        }, 400

    try:
        with db_pipeline.get_connection() as conn:
            result = db_pipeline.archive_old_new_queue_records(
                conn,
                older_than_days=days,
                limit=limit,
                initiated_by=initiated_by,
            )
            counts = db_pipeline.fetch_queue_counts(conn)

        return {
            **result,
            "counts": counts,
            "dbPath": str(db_pipeline.get_db_path()),
        }, 200
    except ValueError as error:
        return {
            "ok": False,
            "error": str(error),
            "dbPath": str(db_pipeline.get_db_path()),
        }, 400
    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
            "dbPath": str(db_pipeline.get_db_path()),
        }, 500


def _persist_publish_status_snapshot(status_snapshot: dict) -> None:
    try:
        with db_pipeline.get_connection() as conn:
            db_pipeline.update_publish_worker_status(conn, status_snapshot)
    except Exception:
        # Keep API behavior resilient even if persistent status write fails.
        pass


def _set_publish_status(updates: dict) -> None:
    with PUBLISH_LOCK:
        PUBLISH_STATUS.update(updates)
        in_memory_snapshot = dict(PUBLISH_STATUS)

    persisted_snapshot: dict = {}
    try:
        with db_pipeline.get_connection() as conn:
            persisted_snapshot = db_pipeline.get_publish_worker_status(conn)
    except Exception:
        persisted_snapshot = {}

    worker_enabled = persisted_snapshot.get("workerEnabled")
    if "workerEnabled" in updates:
        worker_enabled = updates.get("workerEnabled")
    elif worker_enabled is None:
        worker_enabled = in_memory_snapshot.get("workerEnabled")
    if worker_enabled is None:
        worker_enabled = _publish_worker_enabled()

    poll_seconds = persisted_snapshot.get("pollSeconds")
    if "pollSeconds" in updates:
        poll_seconds = updates.get("pollSeconds")
    elif poll_seconds is None:
        poll_seconds = in_memory_snapshot.get("pollSeconds")
    if poll_seconds is None:
        poll_seconds = _publish_poll_seconds()

    snapshot = {
        **in_memory_snapshot,
        "workerEnabled": bool(worker_enabled),
        "pollSeconds": max(30, _env_int(poll_seconds, default=_publish_poll_seconds(), minimum=30, maximum=3600)),
    }
    _persist_publish_status_snapshot(snapshot)


def _get_publish_status() -> dict:
    with PUBLISH_LOCK:
        fallback = dict(PUBLISH_STATUS)

    try:
        with db_pipeline.get_connection() as conn:
            persisted = db_pipeline.get_publish_worker_status(conn)
        merged = {**fallback, **persisted}
    except Exception:
        merged = fallback

    merged["workerEnabled"] = bool(merged.get("workerEnabled")) or _publish_worker_enabled()
    merged["pollSeconds"] = max(
        30,
        _env_int(merged.get("pollSeconds"), default=_publish_poll_seconds(), minimum=30, maximum=3600),
    )
    merged["provider"] = _publish_provider()
    merged["commentFallbackAllowed"] = _facebook_sandbox_allow_comment_fallback()
    merged["twoStepMode"] = "fallback-enabled" if _facebook_sandbox_allow_comment_fallback() else "strict"

    heartbeat_at = _parse_iso_datetime(merged.get("heartbeatAt"))
    stale_after_seconds = max(_publish_worker_stale_min_seconds(), merged["pollSeconds"] * _publish_worker_stale_multiplier())
    if heartbeat_at is not None:
        merged["heartbeatAgeSeconds"] = max(0, int((datetime.now(timezone.utc) - heartbeat_at).total_seconds()))
    else:
        merged["heartbeatAgeSeconds"] = None
    merged["workerStaleAfterSeconds"] = stale_after_seconds
    merged["workerStale"] = bool(merged.get("workerEnabled")) and (
        merged["heartbeatAgeSeconds"] is None or merged["heartbeatAgeSeconds"] > stale_after_seconds
    )

    return merged


def _mock_publish_payload(item: dict) -> dict:
    preview = _build_post_preview(item)
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    obituary_id = str(item.get("id") or "unknown").strip() or "unknown"
    facebook_post_id = f"mock_{now_stamp}_{obituary_id[:8]}"
    comment_url = f"https://mock.facebook.local/comment/{facebook_post_id}"

    return {
        "provider": "mock",
        "facebookPostId": facebook_post_id,
        "commentUrl": comment_url,
        "postedAt": now_iso(),
        "preview": preview,
        "providerResponse": {
            "ok": True,
            "mode": "mock",
            "post_id": facebook_post_id,
            "comment_url": comment_url,
            "page_name": preview.get("pageName"),
        },
    }


def _facebook_sandbox_publish_payload(item: dict) -> dict:
    preview = _build_post_preview(item)

    page_id = str(os.environ.get("FB_PAGE_ID") or "").strip()
    access_token = str(os.environ.get("FB_PAGE_ACCESS_TOKEN") or "").strip()
    if not page_id:
        raise ValueError("FB_PAGE_ID is required for facebook_sandbox provider.")
    if not access_token:
        raise ValueError("FB_PAGE_ACCESS_TOKEN is required for facebook_sandbox provider.")

    image_url = str(preview.get("imageUrl") or "").strip()
    if not image_url:
        raise ValueError("photo_url is required for facebook_sandbox provider.")

    post_text = str(preview.get("postText") or "").strip()
    first_comment_text = str(preview.get("firstCommentText") or "").strip()

    base_url = _facebook_graph_base_url()
    timeout_seconds = _facebook_publish_timeout_seconds()

    photo_endpoint = f"{base_url}/{page_id}/photos"
    photo_payload = {
        "url": image_url,
        "caption": post_text,
        "published": "true",
        "access_token": access_token,
    }
    photo_response = requests.post(photo_endpoint, data=photo_payload, timeout=timeout_seconds)
    if photo_response.status_code >= 400:
        error_summary = _summarize_graph_error(photo_response)
        raise ValueError(f"Facebook photo publish failed: {error_summary}")

    try:
        photo_body = photo_response.json()
    except Exception:
        raise ValueError("Facebook photo publish returned non-JSON response.")

    if not isinstance(photo_body, dict):
        raise ValueError("Facebook photo publish returned invalid payload.")

    photo_object_id = str(photo_body.get("id") or "").strip()
    facebook_post_id = str(photo_body.get("post_id") or photo_object_id or "").strip()
    if not facebook_post_id:
        raise ValueError("Facebook photo publish response missing post ID.")

    comment_body: dict = {}
    comment_id = ""
    comment_warning = ""
    comment_fallback_applied = False
    if first_comment_text:
        comment_endpoint = f"{base_url}/{facebook_post_id}/comments"
        comment_payload = {
            "message": first_comment_text,
            "access_token": access_token,
        }
        try:
            comment_response = requests.post(comment_endpoint, data=comment_payload, timeout=timeout_seconds)
            if comment_response.status_code >= 400:
                error_summary = _summarize_graph_error(comment_response)
                if _facebook_sandbox_allow_comment_fallback() and _is_graph_permission_error(comment_response):
                    comment_warning = error_summary
                    comment_fallback_applied = True
                else:
                    raise ValueError(f"Facebook first-comment publish failed: {error_summary}")

            if not comment_fallback_applied:
                try:
                    parsed_comment = comment_response.json()
                except Exception:
                    raise ValueError("Facebook first-comment publish returned non-JSON response.")

                if not isinstance(parsed_comment, dict):
                    raise ValueError("Facebook first-comment publish returned invalid payload.")

                comment_body = parsed_comment
                comment_id = str(parsed_comment.get("id") or "").strip()
        except Exception as comment_error:
            cleanup_note = ""
            if not _facebook_sandbox_allow_comment_fallback():
                cleanup_target_id = photo_object_id or facebook_post_id
                cleanup_ok, cleanup_error = _delete_facebook_object(
                    base_url=base_url,
                    object_id=cleanup_target_id,
                    access_token=access_token,
                    timeout_seconds=timeout_seconds,
                )
                if cleanup_ok:
                    cleanup_note = " Photo cleanup succeeded after strict comment failure."
                else:
                    cleanup_note = f" Photo cleanup failed after strict comment failure: {cleanup_error}."
            raise ValueError(f"{comment_error}{cleanup_note}") from comment_error

    comment_url = _build_facebook_comment_url(facebook_post_id, comment_id)

    return {
        "provider": "facebook_sandbox",
        "facebookPostId": facebook_post_id,
        "commentUrl": comment_url,
        "postedAt": now_iso(),
        "preview": preview,
        "providerResponse": {
            "ok": True,
            "mode": "facebook_sandbox",
            "graphApiVersion": _facebook_graph_version(),
            "page_id": page_id,
            "post_id": facebook_post_id,
            "comment_id": comment_id or None,
            "comment_fallback_applied": comment_fallback_applied,
            "comment_warning": comment_warning or None,
            "photo_response": {
                "id": photo_body.get("id"),
                "post_id": photo_body.get("post_id"),
            },
            "comment_response": {
                "id": comment_body.get("id") if comment_body else None,
            },
        },
    }


def _build_publish_payload(item: dict, provider: str) -> dict:
    if provider == "mock":
        return _mock_publish_payload(item)
    if provider == "facebook_sandbox":
        return _facebook_sandbox_publish_payload(item)
    raise ValueError(
        "Unsupported FB_PUBLISH_PROVIDER. Supported values: mock, facebook_sandbox."
    )


class PublishFailure(Exception):
    def __init__(self, message: str, recovery: dict | None = None):
        super().__init__(message)
        self.recovery = recovery or {}


def _publish_single_item(conn, obituary_id: str, initiated_by: str) -> dict:
    item = db_pipeline.fetch_queue_item(conn, obituary_id=obituary_id)
    if not item:
        raise ValueError(f"Obituary not found for ID: {obituary_id}")

    original_status = str(item.get("queue_status") or "").strip().lower()
    queue_status = original_status
    if queue_status == "staged":
        # Fast path for staged items: auto-transition to scheduled before publish.
        auto_scheduled_for = (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat()
        db_pipeline.transition_post_queue_status(
            conn,
            obituary_ids=[str(item.get("id") or obituary_id)],
            to_status="scheduled",
            scheduled_for=auto_scheduled_for,
            metadata_extra={
                "publishNowAutoSchedule": True,
                "publishNowAutoScheduledFor": auto_scheduled_for,
            },
            initiated_by=f"{initiated_by}_auto_schedule",
        )
        refreshed = db_pipeline.fetch_queue_item(conn, obituary_id=obituary_id)
        if not refreshed:
            raise ValueError(f"Obituary not found for ID: {obituary_id}")
        item = refreshed
        queue_status = "scheduled"

    if queue_status != "scheduled":
        raise ValueError(
            "Publish now requires staged or scheduled status. "
            f"Current status: {queue_status or 'unknown'}"
        )

    provider = _publish_provider()
    try:
        publish_result = _build_publish_payload(item=item, provider=provider)
        provider_response = publish_result.get("providerResponse") if isinstance(publish_result, dict) else {}
        if not isinstance(provider_response, dict):
            provider_response = {}
        preview_payload = publish_result.get("preview") if isinstance(publish_result, dict) else {}
        if not isinstance(preview_payload, dict):
            preview_payload = {}

        transition_metadata = {
            "provider": provider,
            "twoStepStrict": not _facebook_sandbox_allow_comment_fallback(),
            "firstCommentConfigured": bool(str(preview_payload.get("firstCommentText") or "").strip()),
            "commentPosted": bool(str(provider_response.get("comment_id") or "").strip()),
            "commentFallbackApplied": bool(provider_response.get("comment_fallback_applied")),
            "commentWarning": str(provider_response.get("comment_warning") or "").strip() or None,
            "graphApiVersion": provider_response.get("graphApiVersion"),
        }

        transition = db_pipeline.transition_post_queue_status(
            conn,
            obituary_ids=[str(item.get("id") or obituary_id)],
            to_status="posted",
            posted_at=publish_result["postedAt"],
            facebook_post_id=publish_result["facebookPostId"],
            comment_url=publish_result["commentUrl"],
            retry_count=0,
            retry_at="",
            metadata_extra=transition_metadata,
            initiated_by=initiated_by,
        )

        return {
            "ok": True,
            "obituaryId": item.get("id") or obituary_id,
            "fromStatus": original_status,
            "toStatus": "posted",
            "provider": provider,
            "publish": publish_result,
            "transition": transition,
        }
    except Exception as error:
        error_message = str(error)
        current_retry_count = 0
        try:
            current_retry_count = max(0, int(item.get("retry_count") or 0))
        except Exception:
            current_retry_count = 0

        retry_max_attempts = _publish_retry_max_attempts()
        retry_delay_seconds = _publish_retry_delay_seconds()
        next_retry_count = min(retry_max_attempts, current_retry_count + 1)
        retry_exhausted = next_retry_count >= retry_max_attempts
        next_retry_at = (
            (datetime.now(timezone.utc) + timedelta(seconds=retry_delay_seconds)).isoformat()
            if not retry_exhausted
            else None
        )

        recovery_payload: dict = {
            "ok": False,
            "toStatus": "staged",
            "error": "Recovery was not attempted.",
        }
        try:
            recovery_transition = db_pipeline.transition_post_queue_status(
                conn,
                obituary_ids=[str(item.get("id") or obituary_id)],
                to_status="staged",
                last_error=error_message,
                retry_count=next_retry_count,
                retry_at=next_retry_at,
                metadata_extra={
                    "retryCount": next_retry_count,
                    "retryMaxAttempts": retry_max_attempts,
                    "retryExhausted": retry_exhausted,
                    "retryAt": next_retry_at,
                },
                initiated_by=f"{initiated_by}_publish_failure",
            )
            recovery_payload = {
                "ok": True,
                "toStatus": "staged",
                "retryCount": next_retry_count,
                "retryMaxAttempts": retry_max_attempts,
                "retryExhausted": retry_exhausted,
                "retryAt": next_retry_at,
                "transition": recovery_transition,
            }
        except Exception as recovery_error:
            recovery_payload = {
                "ok": False,
                "toStatus": "staged",
                "error": str(recovery_error),
            }

        raise PublishFailure(
            f"Publish failed for obituary {item.get('id') or obituary_id}: {error_message}",
            recovery=recovery_payload,
        ) from error


def publish_now(obituary_id: str, initiated_by: str = "ui_publish_now") -> tuple[dict, int]:
    try:
        with db_pipeline.get_connection() as conn:
            result = _publish_single_item(conn, obituary_id=obituary_id, initiated_by=initiated_by)
            counts = db_pipeline.fetch_queue_counts(conn)

        warnings = _collect_publish_warnings([result])
        completed_at = now_iso()
        _set_publish_status(
            {
                "state": "completed",
                "message": f"Processed 1 item with {len(warnings)} warning(s).",
                "finishedAt": completed_at,
                "processed": 1,
                "published": 1,
                "failed": 0,
                "lastError": None,
                "workerMode": "publish_now",
                "heartbeatAt": completed_at,
                "lastRun": {
                    "startedAt": completed_at,
                    "finishedAt": completed_at,
                    "processed": 1,
                    "published": 1,
                    "failed": 0,
                    "warningCount": len(warnings),
                    "partialSuccess": sum(1 for warning in warnings if warning.get("commentFallbackApplied")),
                    "warnings": warnings[:5],
                },
            }
        )

        return {
            **result,
            "counts": counts,
            "dbPath": str(db_pipeline.get_db_path()),
        }, 200
    except PublishFailure as error:
        counts = {}
        try:
            with db_pipeline.get_connection() as conn:
                counts = db_pipeline.fetch_queue_counts(conn)
        except Exception:
            counts = {}
        return {
            "ok": False,
            "error": str(error),
            "recovery": error.recovery,
            "counts": counts,
            "dbPath": str(db_pipeline.get_db_path()),
        }, 500
    except ValueError as error:
        return {
            "ok": False,
            "error": str(error),
            "dbPath": str(db_pipeline.get_db_path()),
        }, 400
    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
            "dbPath": str(db_pipeline.get_db_path()),
        }, 500


def run_due_mock_publish(limit: int = 25, initiated_by: str = "mock_publish_worker") -> tuple[dict, int]:
    lock_name = "publish_due_runner"
    lock_owner = f"{initiated_by}:{uuid.uuid4().hex}"
    lock_acquired = False

    try:
        with db_pipeline.get_connection() as conn:
            lock_acquired = db_pipeline.acquire_runtime_lock(
                conn,
                lock_name=lock_name,
                owner_id=lock_owner,
                ttl_seconds=max(120, _publish_poll_seconds() * 2),
                metadata={"initiatedBy": initiated_by},
            )
    except Exception as error:
        return {
            "ok": False,
            "error": f"Failed to acquire publish lock: {error}",
            "status": _get_publish_status(),
            "dbPath": str(db_pipeline.get_db_path()),
        }, 500

    if not lock_acquired:
        return {
            "ok": False,
            "error": "Publish worker is already running.",
            "status": _get_publish_status(),
            "dbPath": str(db_pipeline.get_db_path()),
        }, 409

    _set_publish_status(
        {
            "state": "running",
            "message": "Processing due scheduled posts...",
            "startedAt": now_iso(),
            "finishedAt": None,
            "processed": 0,
            "published": 0,
            "failed": 0,
            "lastError": None,
            "workerMode": "due_runner",
            "heartbeatAt": now_iso(),
        }
    )

    try:
        due_items: list[dict] = []
        now_utc = now_iso()
        with db_pipeline.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT obituary_id
                FROM post_queue
                WHERE status = 'scheduled'
                  AND scheduled_for IS NOT NULL
                  AND scheduled_for <= ?
                ORDER BY scheduled_for ASC
                LIMIT ?
                """,
                (now_utc, max(1, int(limit))),
            ).fetchall()
            due_items = [dict(row) for row in rows]

            results: list[dict] = []
            failures: list[dict] = []
            for row in due_items:
                obituary_id = str(row.get("obituary_id") or "").strip()
                if not obituary_id:
                    continue
                try:
                    published = _publish_single_item(conn, obituary_id=obituary_id, initiated_by=initiated_by)
                    results.append(published)
                except PublishFailure as error:
                    failures.append(
                        {
                            "obituaryId": obituary_id,
                            "error": str(error),
                            "recovery": error.recovery,
                        }
                    )
                except Exception as error:
                    failures.append({"obituaryId": obituary_id, "error": str(error)})

            counts = db_pipeline.fetch_queue_counts(conn)

        warnings = _collect_publish_warnings(results)
        warning_count = len(warnings)
        partial_success_count = sum(1 for warning in warnings if warning.get("commentFallbackApplied"))
        run_message = f"Processed {len(due_items)} due item(s)."
        if warning_count:
            run_message = f"Processed {len(due_items)} due item(s) with {warning_count} warning(s)."

        completed_at = now_iso()
        _set_publish_status(
            {
                "state": "completed",
                "message": run_message,
                "finishedAt": completed_at,
                "processed": len(due_items),
                "published": len(results),
                "failed": len(failures),
                "lastError": failures[0]["error"] if failures else None,
                "heartbeatAt": completed_at,
                "lastRun": {
                    "startedAt": PUBLISH_STATUS.get("startedAt"),
                    "finishedAt": completed_at,
                    "processed": len(due_items),
                    "published": len(results),
                    "failed": len(failures),
                    "warningCount": warning_count,
                    "partialSuccess": partial_success_count,
                    "warnings": warnings[:10],
                },
            }
        )

        return {
            "ok": True,
            "processed": len(due_items),
            "published": len(results),
            "failed": len(failures),
            "results": results,
            "failures": failures,
            "counts": counts,
            "status": _get_publish_status(),
            "dbPath": str(db_pipeline.get_db_path()),
        }, 200
    except Exception as error:
        _set_publish_status(
            {
                "state": "error",
                "message": f"Publish worker failed: {error}",
                "finishedAt": now_iso(),
                "lastError": str(error),
                "heartbeatAt": now_iso(),
            }
        )
        return {
            "ok": False,
            "error": str(error),
            "status": _get_publish_status(),
            "dbPath": str(db_pipeline.get_db_path()),
        }, 500
    finally:
        try:
            with db_pipeline.get_connection() as conn:
                db_pipeline.release_runtime_lock(
                    conn,
                    lock_name=lock_name,
                    owner_id=lock_owner,
                )
        except Exception:
            pass

# Load the obituary data
def load_obituary_data():
    """Load the unified obituary dataset."""
    try:
        data_path = os.path.join(BASE_DIR, 'website_obituaries.json')
        with open(data_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": "Obituary data not found. Please run bundle_for_website.py first."}

@app.route('/')
def index():
    """Serve the main website page."""
    try:
        html_path = os.path.join(BASE_DIR, 'website_preview.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        return """
        <h1>Obituary Website</h1>
        <p>HTML preview file not found. Please ensure website_preview.html exists.</p>
        <p><a href="/api/obituaries">View API Data</a></p>
        """

@app.route('/api/obituaries')
def get_obituaries():
    """API endpoint to get all obituaries."""
    data = load_obituary_data()
    return jsonify(data)

@app.route('/api/obituaries/recent')
def get_recent_obituaries():
    """API endpoint to get recent obituaries (last 20)."""
    data = load_obituary_data()
    if "obituaries" in data:
        recent = data["obituaries"][:20]  # Already sorted by date
        return jsonify({
            "summary": data.get("summary", {}),
            "obituaries": recent,
            "count": len(recent)
        })
    return jsonify(data)

@app.route('/api/funeral-homes')
def get_funeral_homes():
    """API endpoint to get funeral home statistics."""
    data = load_obituary_data()
    if "summary" in data and "funeral_homes" in data["summary"]:
        return jsonify(data["summary"]["funeral_homes"])
    return jsonify({"error": "No funeral home data found"})

@app.route('/api/obituaries/funeral-home/<home_name>')
def get_obituaries_by_home(home_name):
    """API endpoint to get obituaries for a specific funeral home."""
    data = load_obituary_data()
    if "obituaries" in data:
        filtered = [obit for obit in data["obituaries"] if obit.get("funeral_home") == home_name]
        return jsonify({
            "funeral_home": home_name,
            "obituaries": filtered,
            "count": len(filtered)
        })
    return jsonify({"error": "No obituary data found"})

@app.route('/api/status')
def get_status():
    """API endpoint to get system status."""
    data = load_obituary_data()
    if "summary" in data:
        summary = data["summary"]
        return jsonify({
            "status": "active",
            "total_obituaries": summary.get("total_obituaries", 0),
            "working_funeral_homes": summary.get("working_funeral_homes", 0),
            "last_updated": summary.get("generated_at", "Unknown"),
            "funeral_homes": summary.get("funeral_homes", {})
        })
    return jsonify({"status": "error", "message": "Data not available"})


@app.route('/api/scrape/status')
def get_scrape_status():
    with SCRAPE_LOCK:
        return jsonify(dict(SCRAPE_STATUS))


@app.route('/api/scrape/start', methods=['POST'])
def start_scrape():
    with SCRAPE_LOCK:
        if SCRAPE_STATUS.get("state") == "running":
            return jsonify({"error": "Scrape already running", "status": dict(SCRAPE_STATUS)}), 409
        SCRAPE_STATUS.update(
            {
                "state": "running",
                "message": "Starting scrape...",
                "startedAt": now_iso(),
                "finishedAt": None,
                "totalSources": 0,
                "completedSources": 0,
                "currentSourceKey": None,
                "currentSourceName": None,
                "safeMode": False,
                "skippedSources": 0,
                "totalObituaries": 0,
                "sources": [],
                "dbSync": None,
            }
        )

    worker = threading.Thread(target=run_scrape_job, daemon=True)
    worker.start()
    return jsonify({"ok": True, "message": "Scrape started"})


@app.route('/api/db/obituaries')
def get_db_obituaries():
    default_status = (os.environ.get("DB_DEFAULT_STATUS_FILTER") or "").strip() or None
    query_status = request.args.get("status")
    status = _normalize_queue_status(query_status)
    if query_status and status is None:
        return jsonify(
            {
                "ok": False,
                "error": f"Invalid queue status: {query_status}",
                "allowedStatuses": sorted(db_pipeline.QUEUE_STATUSES),
                "dbPath": str(db_pipeline.get_db_path()),
                "obituaries": [],
            }
        ), 400

    payload = load_db_feed(limit=_parse_limit_arg(default=200), status=status or default_status)
    return jsonify(payload)


@app.route('/api/db/obituaries/recent')
def get_db_recent_obituaries():
    payload = load_db_feed(limit=20)
    return jsonify(payload)


@app.route('/api/db/queue/new')
def get_db_queue_new():
    payload, status_code = load_db_feed_for_status("new", limit=_parse_limit_arg(default=200))
    return jsonify(payload), status_code


@app.route('/api/db/queue/staged')
def get_db_queue_staged():
    payload, status_code = load_db_feed_for_status("staged", limit=_parse_limit_arg(default=200))
    return jsonify(payload), status_code


@app.route('/api/db/queue/scheduled')
def get_db_queue_scheduled():
    payload, status_code = load_db_feed_for_status("scheduled", limit=_parse_limit_arg(default=200))
    return jsonify(payload), status_code


@app.route('/api/db/queue/posted')
def get_db_queue_posted():
    payload, status_code = load_db_feed_for_status("posted", limit=_parse_limit_arg(default=200))
    return jsonify(payload), status_code


@app.route('/api/db/queue/archived')
def get_db_queue_archived():
    payload, status_code = load_db_feed_for_status("archived", limit=_parse_limit_arg(default=200))
    return jsonify(payload), status_code


@app.route('/api/db/queue/counts')
def get_db_queue_counts():
    payload, status_code = load_db_queue_counts()
    return jsonify(payload), status_code


@app.route('/api/db/queue/history')
def get_db_queue_history():
    payload, status_code = load_db_queue_history(limit=_parse_limit_arg(default=100))
    return jsonify(payload), status_code


@app.route('/api/db/queue/post-preview/settings')
def get_db_queue_post_preview_settings():
    return jsonify(
        {
            "ok": True,
            "settings": dict(POST_PREVIEW_SETTINGS),
        }
    )


@app.route('/api/db/queue/post-preview/settings', methods=['POST'])
def update_db_queue_post_preview_settings():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}

    updates, errors = _coerce_preview_settings_updates(payload)
    if errors:
        return jsonify({"ok": False, "error": "; ".join(errors), "settings": dict(POST_PREVIEW_SETTINGS)}), 400

    if not updates:
        return jsonify({"ok": False, "error": "No valid settings provided.", "settings": dict(POST_PREVIEW_SETTINGS)}), 400

    POST_PREVIEW_SETTINGS.update(updates)
    return jsonify({"ok": True, "settings": dict(POST_PREVIEW_SETTINGS)})


@app.route('/api/db/queue/<obituary_id>/history')
def get_db_queue_history_for_obituary(obituary_id: str):
    payload, status_code = load_db_queue_history(
        limit=_parse_limit_arg(default=100),
        obituary_id=obituary_id,
    )
    return jsonify(payload), status_code


@app.route('/api/db/queue/<obituary_id>/post-preview')
def get_db_queue_post_preview(obituary_id: str):
    payload, status_code = load_db_post_preview(obituary_id=obituary_id)
    return jsonify(payload), status_code


@app.route('/api/db/queue/<obituary_id>/overrides')
def get_db_queue_overrides(obituary_id: str):
    body, status_code = load_db_queue_override(obituary_id=obituary_id)
    return jsonify(body), status_code


@app.route('/api/db/queue/<obituary_id>/overrides', methods=['POST'])
def save_db_queue_overrides(obituary_id: str):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    body, status_code = save_db_queue_override(obituary_id=obituary_id, payload=payload)
    return jsonify(body), status_code


@app.route('/api/db/source-health')
def get_db_source_health():
    return jsonify(load_db_source_health())


@app.route('/api/db/source-health/action-required')
def get_db_action_required_sources():
    return jsonify(load_db_action_required())


@app.route('/api/db/publish/status')
def get_publish_status():
    return jsonify({"ok": True, "status": _get_publish_status()})


@app.route('/api/db/publish/preflight')
def get_publish_preflight():
    deep = _env_bool(request.args.get("deep"), default=False)
    initiated_by = str(request.args.get("initiatedBy") or "api_publish_preflight").strip() or "api_publish_preflight"
    body, status_code = run_publish_preflight(deep=deep, initiated_by=initiated_by)
    return jsonify(body), status_code


@app.route('/api/db/publish/preflight/latest')
def get_publish_preflight_latest():
    latest = _load_latest_publish_preflight_run()
    return jsonify(
        {
            "ok": latest is not None,
            "latest": latest,
            "dbPath": str(db_pipeline.get_db_path()),
        }
    )


@app.route('/api/db/ops/health')
def get_operational_health():
    status = _get_publish_status()
    body = _build_publish_operational_health(status)
    return jsonify(body), 200


@app.route('/api/db/secrets/status')
def get_secret_lifecycle_status():
    return jsonify(
        {
            "ok": True,
            "status": _build_secret_lifecycle_status(),
            "dbPath": str(db_pipeline.get_db_path()),
        }
    ), 200


@app.route('/api/db/publish/now/<obituary_id>', methods=['POST'])
def publish_db_queue_single(obituary_id: str):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    initiated_by = str(payload.get("initiatedBy") or "ui_publish_now").strip() or "ui_publish_now"
    body, status_code = publish_now(obituary_id=obituary_id, initiated_by=initiated_by)
    return jsonify(body), status_code


@app.route('/api/db/publish/run-due', methods=['POST'])
def publish_db_queue_due():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    raw_limit = payload.get("limit", 25)
    try:
        limit = max(1, min(int(raw_limit), 200))
    except Exception:
        limit = 25
    initiated_by = str(payload.get("initiatedBy") or "mock_publish_worker").strip() or "mock_publish_worker"
    body, status_code = run_due_mock_publish(limit=limit, initiated_by=initiated_by)
    return jsonify(body), status_code


@app.route('/api/db/queue/transition', methods=['POST'])
def transition_db_queue():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    body, status_code = transition_db_queue_records(payload)
    return jsonify(body), status_code


@app.route('/api/db/queue/archive-old-new', methods=['POST'])
def archive_db_queue_old_new():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    body, status_code = archive_old_new_queue_records(payload)
    return jsonify(body), status_code


@app.route('/api/db/queue/<obituary_id>/transition', methods=['POST'])
def transition_db_queue_single(obituary_id: str):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = {}
    payload["obituaryId"] = obituary_id
    body, status_code = transition_db_queue_records(payload)
    return jsonify(body), status_code

if __name__ == '__main__':
    print("🌐 Starting Obituary Website Server...")
    print("=" * 50)
    
    # Check if data files exist
    data_path = os.path.join(BASE_DIR, 'website_obituaries.json')
    if os.path.exists(data_path):
        data = load_obituary_data()
        if "summary" in data:
            summary = data["summary"]
            print(f"📊 Loaded {summary.get('total_obituaries', 0)} obituaries")
            print(f"🏠 From {summary.get('working_funeral_homes', 0)} funeral homes")
            print(f"📅 Last updated: {summary.get('generated_at', 'Unknown')}")
        print("✅ Data loaded successfully!")
    else:
        print("⚠️  website_obituaries.json not found")
        print("   Run 'py bundle_for_website.py' first to create the dataset")
    
    print("\n🚀 Server starting...")
    port = int(os.environ.get('PORT', 5000))
    print(f"   📱 Website: http://localhost:{port}")
    print(f"   🔗 API: http://localhost:{port}/api/obituaries")
    print(f"   📊 Status: http://localhost:{port}/api/status")
    print("\n   Press Ctrl+C to stop the server")
    print("=" * 50)
    
    try:
        app.run(debug=False, host='0.0.0.0', port=port)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        print("💡 You may need to install Flask: pip install flask flask-cors")
