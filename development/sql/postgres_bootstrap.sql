BEGIN;

CREATE TABLE IF NOT EXISTS obituaries (
    id TEXT PRIMARY KEY,
    source_key TEXT NOT NULL,
    source_name TEXT NOT NULL,
    listing_url TEXT,
    obituary_url TEXT NOT NULL UNIQUE,
    name TEXT,
    birth_date TEXT,
    death_date TEXT,
    age INTEGER,
    summary TEXT,
    photo_url TEXT,
    scraped_at TEXT,
    raw_hash TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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
    override_name TEXT,
    override_birth_date TEXT,
    override_death_date TEXT,
    override_reason TEXT,
    override_updated_at TEXT,
    override_updated_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CONSTRAINT fk_post_queue_obituary
        FOREIGN KEY(obituary_id)
        REFERENCES obituaries(id)
        ON DELETE CASCADE,
    CONSTRAINT chk_post_queue_status
        CHECK (status IN ('new', 'staged', 'scheduled', 'posted', 'archived'))
);

CREATE INDEX IF NOT EXISTS idx_post_queue_status ON post_queue(status);
CREATE INDEX IF NOT EXISTS idx_post_queue_scheduled_for ON post_queue(scheduled_for);
CREATE INDEX IF NOT EXISTS idx_post_queue_retry_at ON post_queue(retry_at);

CREATE TABLE IF NOT EXISTS queue_transition_audit (
    id BIGSERIAL PRIMARY KEY,
    obituary_id TEXT NOT NULL,
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    action_at TEXT NOT NULL,
    initiated_by TEXT,
    metadata_json TEXT,
    CONSTRAINT fk_queue_transition_obituary
        FOREIGN KEY(obituary_id)
        REFERENCES post_queue(obituary_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_queue_transition_audit_obituary_id ON queue_transition_audit(obituary_id);
CREATE INDEX IF NOT EXISTS idx_queue_transition_audit_action_at ON queue_transition_audit(action_at);

CREATE TABLE IF NOT EXISTS publish_worker_status (
    id INTEGER PRIMARY KEY,
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
    updated_at TEXT NOT NULL,
    CONSTRAINT chk_publish_worker_status_singleton CHECK (id = 1)
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
    id BIGSERIAL PRIMARY KEY,
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
    id BIGSERIAL PRIMARY KEY,
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
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL,
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
    CONSTRAINT fk_scrape_source_status_run
        FOREIGN KEY(run_id)
        REFERENCES scrape_runs(id)
        ON DELETE CASCADE
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
    run_id BIGINT NOT NULL,
    checked_at TEXT NOT NULL,
    CONSTRAINT fk_scrape_source_latest_run
        FOREIGN KEY(run_id)
        REFERENCES scrape_runs(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scrape_source_latest_freshness ON scrape_source_latest(freshness_status);

COMMIT;