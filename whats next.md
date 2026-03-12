# Whats Next

This document expands the Grounding Doc using the current app build and defines the next implementation steps.

## 1) Current Build Snapshot (March 2026)

The app already has a working end-to-end operational baseline:

- Scrape pipeline writes selected obituary output and ingests into SQLite at data/app.db.
- Queue state machine exists in SQLite via post_queue with statuses:
  - new
  - staged
  - scheduled
  - posted
  - archived
- Queue transitions are enforced in code and audited in queue_transition_audit.
- Website/admin preview already supports:
  - queue tabs
  - transition actions
  - mandatory future scheduledFor validation when moving to scheduled
  - post preview template controls
  - transition history
  - source health views
- Publish flow now supports:
  - `mock` provider (local/dev)
  - `facebook_sandbox` provider (Graph API)
  - single publish now
  - run due scheduled items
- Daily scraping automation exists through PowerShell + Task Scheduler scripts.

## 2) Grounding Doc Alignment (Using SQLite)

We will keep SQLite as the primary database for now and align naming/workflow to Grounding Doc behavior.

Status mapping:

- Recent (Grounding) -> new (current)
- Staged (Grounding) -> staged (current)
- Scheduled (Grounding) -> scheduled (current)
- Posted (Grounding) -> posted (current)
- Archived is kept as an internal retention state for older records.

Field mapping:

- full_name -> name
- dob -> birth_date
- dod -> death_date
- original_url -> obituary_url
- image_url -> photo_url
- scheduled_at -> scheduled_for

## 3) Key Gaps To Close

1. Staged override persistence and UI editing are implemented; remaining work is stronger operator validation/audit visibility in the staged flow.
2. Continuous worker is running with locking and heartbeat; remaining hardening is stale-worker alerting and service health alarms.
3. Strict two-step sandbox publish is now validated end-to-end (`commentFallbackApplied=false`); remaining work is token lifecycle management and continuous preflight gating in UI.
4. Strict failure cleanup now prevents orphan photo posts when comment publish fails; remaining work is capped retry policy and clearer failure badges/triage UX.
5. Deduplication rule from Grounding Doc (full_name + dod within 30-day window) is not yet implemented as an ingest gate.
6. `confidence_score` and auto-stage/auto-schedule suggestions are not yet implemented.
7. Grounding Doc target database is PostgreSQL; current system is SQLite-first and needs a migration plan/execution phase.

## 4) Future Additions and Changes

## Phase A - Workflow Canonicalization

Goal: make UI and API language match Grounding Doc while preserving current internals.

Changes:

- Add UI labels that show Recent/Staged/Scheduled/Posted while continuing to store new/staged/scheduled/posted.
- Add a small translation layer in API responses to include both internal and display status.
- Keep archived hidden from primary operator flow unless explicitly viewing historical records.

Done when:

- Operators can work entirely in Grounding status language in UI.
- Existing API clients using new/staged/scheduled/posted continue to work.

## Phase B - Staged Editing Suite

Goal: support manual correction before scheduling.

Changes:

- Add override columns or a dedicated obituary_overrides table for:
  - override_name
  - override_birth_date
  - override_death_date
  - override_reason
  - override_updated_at
  - override_updated_by
- Update feed/query functions to expose effective values (override first, scraped fallback).
- Add staged-tab edit controls and save endpoint.

Done when:

- Admin can edit Name, DOB, DOD in staged tab and see changes reflected in post preview.
- Transition history records who changed values and when.

## Phase C - Scheduled Publish Worker (1-5 minute polling)

Goal: unattended due-post processing.

Changes:

- Add worker entrypoint script (for example, publish_worker.py) that loops every N minutes.
- Reuse existing due-processing logic and add lock to prevent concurrent runs.
- Add Task Scheduler registration script for worker startup/restart on Windows.
- Add environment flags:
  - PUBLISH_WORKER_ENABLED
  - PUBLISH_POLL_SECONDS
  - FB_PUBLISH_PROVIDER

Done when:

- scheduled items with scheduled_for <= now are moved automatically without manual button clicks.
- Worker status is visible in existing publish status endpoint.

## Phase D - Facebook Graph API Two-Step Publish (Sandbox First)

Goal: replace mock publish path with real integration.

Changes:

- Implement provider module with strict sequence:
  1) Create native photo post from photo_url with caption:
     - [Full Name]
     - [DOB] - [DOD]
  2) Post first comment containing obituary_url
- Store returned post_id and comment URL in queue record.
- Keep mock provider for local development and tests.
- Add provider routing:
  - mock
  - facebook_sandbox
  - facebook_live (future)

Done when:

- Sandbox page receives image post and first comment URL from scheduled jobs.
- Queue record captures facebook_post_id, comment_url, posted_at.

## Phase E - Error Handling and Recovery

Goal: no silent publish failures.

Changes:

- On publish failure:
  - set last_error
  - transition scheduled -> staged
  - write audit metadata with provider error payload (sanitized)
- Add optional retry policy with capped attempts.
- Add UI badges for records requiring review.

Done when:

- Any provider failure automatically returns record to staged and is visible in UI.

## Phase F - Deduplication and Confidence Scoring

Goal: reduce operator workload and duplicate posts.

Changes:

- Add dedupe rule at ingest:
  - normalize name
  - compare death_date
  - detect matches within 30-day window
- Add dedupe flags:
  - is_duplicate_candidate
  - duplicate_of_obituary_id
  - dedupe_confidence
- Add confidence_score field for automation readiness.
- Add suggestion-only flags first:
  - suggest_auto_stage
  - suggest_auto_schedule

Done when:

- Duplicate candidates are surfaced before entering primary queue.
- High-confidence records are clearly suggested, not auto-posted by default.

## 5) Implementation Order (Recommended)

1. Phase B (Staged editing suite)
2. Phase E (Failure recovery)
3. Phase C (Continuous worker)
4. Phase D (Facebook sandbox integration)
5. Phase F (Dedupe + confidence scoring)
6. Phase A polish (label harmonization and docs cleanup)

Reason for this order:

- Editing + recovery protect quality first.
- Worker + sandbox integration unlocks automation safely.
- Dedupe/scoring then reduce manual effort and improve throughput.

## 6) Immediate Next Sprint Backlog

- Completed in latest cycle:
  - publish preflight status surfacing/gating in UI flows
  - capped retry model foundation (`retry_count` / `retry_at`) with failure triage visibility in queue data
  - operator-facing failure filters/badges for publish recovery workflows
  - token/permission drift monitoring via scheduled deep preflight checks
  - Python-native `.env` loading for server/worker startup to avoid shell-specific environment drift

- Still open:
  - dedupe gate (name + DOD within 30 days) and duplicate candidate flags at ingest
  - `confidence_score` and suggestion flags (`suggest_auto_stage`, `suggest_auto_schedule`) as non-blocking hints
  - PostgreSQL migration plan and compatibility layer (schema parity, repository abstraction, migration scripts)
  - integration test checklist for:
    - publish preflight endpoint (lightweight + deep)
    - strict publish success path (photo + comment)
    - strict comment failure rollback cleanup (no orphan post)
    - worker due processing and lock behavior
    - staged edit persistence and schedule validation

## 7) Non-Goals Right Now

- PostgreSQL migration (explicitly deferred while SQLite remains stable).
- Fully autonomous auto-scheduling without human review.
- Replacing existing scraper stack.

## 8) Success Metrics

- Zero manual button-click requirement for due scheduled publishing.
- 100 percent of publish failures return to staged with visible error context.
- At least 80 percent of staged corrections performed through in-app override controls (not JSON edits).
- Duplicate candidate false-positive rate monitored and tuned over time.

## 9) Phase C Implementation Update (March 10, 2026)

Implemented:

- Added persistent publish worker status storage in SQLite (`publish_worker_status`) and exposed worker runtime metadata through existing publish status API.
- Added cross-process runtime lock table (`runtime_locks`) and lock helpers to prevent concurrent due-publish runs.
- Updated due publish runner to use DB-backed lock acquisition/release and persist status snapshots.
- Added environment-driven worker configuration support:
  - `PUBLISH_WORKER_ENABLED`
  - `PUBLISH_POLL_SECONDS`
  - `FB_PUBLISH_PROVIDER`
- Added standalone worker entrypoint:
  - `publish_worker.py` (continuous polling loop with heartbeat/status updates)
- Added Windows automation helpers:
  - `run_publish_worker.ps1`
  - `register_publish_worker_task.ps1` (Task Scheduler at startup + auto-restart)

Notes:

- Existing manual publish trigger (`/api/db/publish/run-due`) remains available.
- Continuous worker can run as a separate process without losing status visibility in the API.

Operational validation completed:

- Registered and started Task Scheduler worker task (`ObitScraper-PublishWorker`) on the local machine.
- Confirmed worker process startup log creation via `logs/publish_worker_*.log`.
- Ran end-to-end smoke test: staged -> scheduled (future `scheduled_for`) -> due publish -> posted transition.
- Verified publish status API reflects completed run metadata (`processed`, `published`, `failed`, `lastRun`).

## 10) Phase D Kickoff Update (March 10, 2026)

Implemented:

- Added provider routing in publish flow using `FB_PUBLISH_PROVIDER` with support for:
  - `mock`
  - `facebook_sandbox`
- Added `facebook_sandbox` two-step publish path:
  1) Create photo post on page feed using `photo_url` + caption text.
  2) Create first comment containing obituary URL.
- Added Graph API environment/config support:
  - `FB_PAGE_ID`
  - `FB_PAGE_ACCESS_TOKEN`
  - `FB_GRAPH_API_VERSION`
  - `FB_GRAPH_API_BASE_URL`
  - `FB_PUBLISH_TIMEOUT_SECONDS`
- Kept existing failure recovery behavior so provider errors still transition `scheduled -> staged` with `last_error` populated.
- Added direct API smoke-test script for sandbox publishing:
  - `smoke_test_facebook_sandbox.ps1`
- Added operator runbook section for worker registration, provider switching, and sandbox smoke test in `README.md`.
- Hardened `register_publish_worker_task.ps1` to fail fast and return non-zero when task creation/update fails.
- Added sandbox comment-permission fallback behavior:
  - If photo post succeeds but first-comment fails due permission error, publish still completes with warning metadata.
  - Controlled by `FB_SANDBOX_ALLOW_COMMENT_FALLBACK` (default false / strict mode).
- Fixed publish status persistence merge so fields like `lastError` clear correctly on successful runs.
- Verified sandbox smoke test publishes to posted queue successfully with provider set to `facebook_sandbox`.

## 11) Phase D and Operational Hardening Update (March 10, 2026 - Latest)

Implemented:

- Added strict-mode rollback cleanup for two-step publish:
  - When photo post succeeds but first-comment fails in strict mode, the created photo object is deleted immediately.
  - This prevents orphan Facebook posts without obituary-link comments.
- Added publish preflight API endpoint:
  - `GET /api/db/publish/preflight`
  - `GET /api/db/publish/preflight?deep=true`
- Added deep preflight probe flow:
  - Verifies page lookup and token/page access.
  - Creates unpublished probe post.
  - Creates probe comment.
  - Cleans up probe comment and post.
  - Returns structured pass/fail/warning summary.
- Updated smoke test script to run deep preflight by default before scheduling:
  - Added `-SkipPreflight` override switch.
- Validated strict sandbox publish with updated token scope:
  - Smoke test produced successful two-step publish (`published=1`, `failed=0`, `warningCount=0`).
  - UI-related warning checks remained clean (`lastRun.warningCount=0`, no fallback warning rows).
- Added persistent publish preflight telemetry storage in SQLite:
  - `publish_preflight_runs` table plus latest-run retrieval helpers.
- Added operational health APIs for runtime hardening:
  - `/api/db/ops/health` (stale worker + preflight drift + secret checks)
  - `/api/db/publish/preflight/latest` (latest recorded preflight run)
  - `/api/db/secrets/status` (non-secret lifecycle visibility + token fingerprint)
- Added stale-worker detection logic:
  - heartbeat age, stale thresholds, and alert payloads in publish status/ops health.
- Added scheduled deep preflight in worker loop:
  - env-driven interval (`PUBLISH_PREFLIGHT_DEEP_INTERVAL_SECONDS`) and persisted run records.
- Added Windows operational automation scripts:
  - `run_publish_health_check.ps1`
  - `register_publish_health_task.ps1`
  - extended worker task wiring to pass deep-preflight interval.
- Added secret lifecycle runbook:
  - `SECRET_ROTATION_RUNBOOK.md` with rotation steps, drift checks, and incident note template.

Remaining Work To Fully Match Grounding Targets (Roadmap-Aligned Workstreams):

1) PostgreSQL Migration
- Build SQLite -> PostgreSQL migration plan with schema parity checks.
- Preserve queue transitions, audit history, and publish worker semantics during staged cutover.

2) Retry Policy and Failure Triage UX Polish
- Tune retry heuristics and operator UX around retries (visibility, sort/filter defaults, retry intent signals).
- Expand failure categorization to make manual triage decisions faster.

3) Deduplication Rule (Grounding Section 4)
- Implement ingest-time duplicate candidate detection using normalized full_name + dod within a 30-day window.
- Add duplicate marker fields and review workflow.

4) Confidence Scoring Roadmap (Grounding Section 4)
- Add confidence_score plus non-blocking suggest_auto_stage/suggest_auto_schedule hints.
- Keep manual gatekeeping as default until confidence thresholds are validated.

5) Operational Hardening Follow-Through
- Wire alert sinks/notifications (for example email/webhook) from `/api/db/ops/health` error states.
- Add scheduled ops-health result retention/reporting for trend visibility.

Definition of Continuation (Next Execution Order):

1) Deduplication ingest rule and duplicate review flow.
2) Confidence scoring with suggestion-only automation hints.
3) Retry/failure triage UX polish.
4) PostgreSQL migration planning, then staged cutover once stability checkpoint is met.
5) Ops-health alert sinks and reporting hardening.

## 12) Clear Next Implementation Goal (Queued)

Goal: Implement ingest-time deduplication guardrails in SQLite pipeline (Grounding Section 4) without changing manual gatekeeping defaults.

Implementation target:

- Add duplicate candidate fields (for example `is_duplicate_candidate`, `duplicate_of_obituary_id`, `dedupe_confidence`, `dedupe_reason`) to the ingestion model.
- Detect duplicates using normalized `full_name/name` + `dod/death_date` within a 30-day window during ingest.
- Persist duplicate candidate markers and expose them in queue/feed APIs.
- Add review-friendly metadata so operators can accept/ignore candidates.

Done when:

- Newly ingested likely-duplicate records are clearly marked in DB and visible in API payloads.
- Existing queue transitions continue to work unchanged.
- No automatic suppress/auto-post behavior is introduced; flags are advisory only.

## 13) Frontend Data Sync Validation and Fix (March 11, 2026)

Goal:

- Ensure scraper output is reliably reflected in frontend queue/feed data (SQLite-backed API), not only JSON bundle files.

Issue observed during validation:

- Frontend queue/feed APIs are DB-backed (`/api/db/...`), but common local refresh entrypoints could run scrape + bundle without always syncing selected output into SQLite.
- Legacy SQLite schema state could also block ingestion with `sqlite3.OperationalError: no such column: retry_at` when index creation ran before optional-column migration.

Implemented:

- Added resilient optional-index creation in schema bootstrap:
  - Moved `post_queue.retry_at` index creation behind optional-column checks so older DB files migrate cleanly.
  - File: `db_pipeline.py`
- Updated ingestion CLI to load `.env` before DB resolution so `APP_DB_PATH` behavior matches server/worker startup.
  - File: `ingest_selected_to_db.py`
- Added automatic SQLite sync step (`ingest_selected_to_db.py`) to common refresh entrypoints:
  - `run_app.ps1`
  - `refresh_and_push_data.ps1`
  - New optional switch: `-SkipIngest`

Operational validation completed:

- Pre-fix check showed selected output ahead of DB:
  - selected output count: `172`
  - DB obituaries count: `112`
  - DB latest `scraped_at`: `2026-03-01...`
- Post-fix ingest succeeded and DB updated to latest scrape window:
  - ingestion result: `obituariesUpserted=172`, `sourcesTracked=11`, `status=ok`
  - DB obituaries count: `224`
  - DB queue count: `224`
  - DB `new` queue items: `112`
  - DB latest `scraped_at`: `2026-03-11...`
- Verified launcher path executes DB sync step successfully:
  - `run_app.ps1 -SkipScrape -SkipBundle -NoServer` ran ingest and reported `Status: ok`.

Outcome:

- New obituaries now hit the same SQLite data path consumed by frontend queue/feed APIs.
- Scrape refresh entrypoints are aligned with frontend data source expectations.
