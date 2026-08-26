-- src/back/app_monitor/migrations/V20260702_001__create_monitor_tables.sql
-- Flyway migration for app_monitor

CREATE SCHEMA IF NOT EXISTS app_monitor;

CREATE TABLE IF NOT EXISTS app_monitor.memory_snapshots (
    id              BIGSERIAL PRIMARY KEY,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    app_name        VARCHAR(100) NOT NULL,
    rss_mb          DOUBLE PRECISION NOT NULL,
    vms_mb          DOUBLE PRECISION NOT NULL,
    shared_mb       DOUBLE PRECISION,
    percent         DOUBLE PRECISION NOT NULL,
    requests_count  INTEGER NOT NULL DEFAULT 0,
    peak_rss_mb     DOUBLE PRECISION NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_memory_snapshots_app_ts ON app_monitor.memory_snapshots(app_name, captured_at);
CREATE INDEX IF NOT EXISTS idx_memory_snapshots_ts ON app_monitor.memory_snapshots(captured_at);

CREATE TABLE IF NOT EXISTS app_monitor.request_memory_stats (
    id              BIGSERIAL PRIMARY KEY,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    app_name        VARCHAR(100) NOT NULL,
    method          VARCHAR(10) NOT NULL,
    path            VARCHAR(500) NOT NULL,
    status_code     INTEGER NOT NULL,
    duration_ms     DOUBLE PRECISION NOT NULL,
    rss_before_mb   DOUBLE PRECISION NOT NULL,
    rss_after_mb    DOUBLE PRECISION NOT NULL,
    rss_delta_mb    DOUBLE PRECISION NOT NULL,
    peak_during_mb  DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_req_mem_app_ts ON app_monitor.request_memory_stats(app_name, captured_at);
CREATE INDEX IF NOT EXISTS idx_req_mem_heavy ON app_monitor.request_memory_stats(rss_delta_mb DESC);

CREATE TABLE IF NOT EXISTS app_monitor.memory_alerts (
    id              BIGSERIAL PRIMARY KEY,
    fired_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    app_name        VARCHAR(100) NOT NULL,
    level           VARCHAR(20) NOT NULL,
    rss_mb          DOUBLE PRECISION NOT NULL,
    threshold_mb    DOUBLE PRECISION NOT NULL,
    message         TEXT
);
CREATE INDEX IF NOT EXISTS idx_mem_alerts_ts ON app_monitor.memory_alerts(fired_at DESC);