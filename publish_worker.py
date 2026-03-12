from __future__ import annotations

import os
import signal
import threading
import time
from datetime import datetime, timezone

import db_pipeline
import env_bootstrap
import website_server

_STOP_EVENT = threading.Event()
env_bootstrap.load_env_file()


def _env_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    candidate = str(value).strip().lower()
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


def _deep_preflight_interval_seconds() -> int:
    return _env_int(
        os.environ.get("PUBLISH_PREFLIGHT_DEEP_INTERVAL_SECONDS"),
        default=0,
        minimum=0,
        maximum=86400,
    )


def _set_signal_handlers() -> None:
    def _handle_signal(signum, frame):
        _STOP_EVENT.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)


def _heartbeat(*, enabled: bool, poll_seconds: int, message: str) -> None:
    try:
        with db_pipeline.get_connection() as conn:
            db_pipeline.heartbeat_publish_worker(
                conn,
                worker_mode="publish_worker",
                worker_enabled=enabled,
                poll_seconds=poll_seconds,
                message=message,
            )
    except Exception:
        pass


def _now_label() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def main() -> int:
    _set_signal_handlers()

    enabled = _env_bool(os.environ.get("PUBLISH_WORKER_ENABLED"), default=False)
    poll_seconds = _env_int(os.environ.get("PUBLISH_POLL_SECONDS"), default=300, minimum=30, maximum=3600)
    batch_limit = _env_int(os.environ.get("PUBLISH_WORKER_BATCH_LIMIT"), default=25, minimum=1, maximum=200)
    initiated_by = str(os.environ.get("PUBLISH_WORKER_INITIATED_BY") or "publish_worker_loop").strip() or "publish_worker_loop"
    deep_preflight_interval = _deep_preflight_interval_seconds()
    last_deep_preflight_at = 0.0

    if not enabled:
        message = "Publish worker is disabled (set PUBLISH_WORKER_ENABLED=1 to run)."
        print(f"[{_now_label()}] {message}")
        _heartbeat(enabled=False, poll_seconds=poll_seconds, message=message)
        return 0

    print(
        f"[{_now_label()}] Publish worker started. poll={poll_seconds}s batch_limit={batch_limit} "
        f"provider={website_server._publish_provider()} deep_preflight_interval={deep_preflight_interval}s"
    )
    _heartbeat(enabled=True, poll_seconds=poll_seconds, message="Publish worker started.")

    while not _STOP_EVENT.is_set():
        try:
            if deep_preflight_interval > 0:
                now_seconds = time.time()
                should_run_deep_preflight = last_deep_preflight_at <= 0 or (
                    now_seconds - last_deep_preflight_at >= deep_preflight_interval
                )
                if should_run_deep_preflight:
                    preflight_body, preflight_status = website_server.run_publish_preflight(
                        deep=True,
                        initiated_by=f"{initiated_by}_deep_preflight",
                    )
                    preflight_summary = preflight_body.get("summary") if isinstance(preflight_body, dict) else {}
                    if not isinstance(preflight_summary, dict):
                        preflight_summary = {}
                    preflight_failed = int(preflight_summary.get("failed") or 0)
                    preflight_warnings = int(preflight_summary.get("warnings") or 0)
                    preflight_ok = bool(preflight_body.get("ok")) and preflight_status < 400
                    preflight_message = (
                        f"deep_preflight status={preflight_status} ok={preflight_ok} "
                        f"failed={preflight_failed} warnings={preflight_warnings}"
                    )
                    print(f"[{_now_label()}] {preflight_message}")
                    _heartbeat(enabled=True, poll_seconds=poll_seconds, message=preflight_message)
                    last_deep_preflight_at = now_seconds

            body, status_code = website_server.run_due_mock_publish(limit=batch_limit, initiated_by=initiated_by)
            processed = int(body.get("processed") or 0)
            published = int(body.get("published") or 0)
            failed = int(body.get("failed") or 0)
            message = f"run_due status={status_code} processed={processed} published={published} failed={failed}"
            print(f"[{_now_label()}] {message}")
            _heartbeat(enabled=True, poll_seconds=poll_seconds, message=message)
        except Exception as error:
            message = f"worker iteration failed: {error}"
            print(f"[{_now_label()}] {message}")
            _heartbeat(enabled=True, poll_seconds=poll_seconds, message=message)

        for _ in range(poll_seconds):
            if _STOP_EVENT.is_set():
                break
            time.sleep(1)

    stop_message = "Publish worker stopped."
    print(f"[{_now_label()}] {stop_message}")
    _heartbeat(enabled=True, poll_seconds=poll_seconds, message=stop_message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
