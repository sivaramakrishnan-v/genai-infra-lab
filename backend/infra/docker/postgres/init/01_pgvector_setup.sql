-- ===========================================================
-- Extensions
-- ===========================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

-- ===========================================================
-- 1) log_master (ingest tracking)
-- ===========================================================
CREATE TABLE IF NOT EXISTS log_master (
    id              BIGSERIAL PRIMARY KEY,    -- sequential ID

    source_type     TEXT NOT NULL,            -- 'file_upload', 'api', 's3'
    source_name     TEXT,                     -- filename or S3 key

    service_name    TEXT,                     -- optional, provided or inferred
    environment     TEXT,                     -- dev / qa / prod
    log_format      TEXT,                     -- java, python, otel, etc.

    line_count      INTEGER,                  -- # lines parsed
    byte_size       BIGINT,                   -- raw file size

    parse_status    TEXT NOT NULL DEFAULT 'pending',
                                                -- pending / in_progress / partial / failed / completed

    parse_error     TEXT,                     -- store parser error message

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    parsed_at       TIMESTAMPTZ
);

COMMENT ON TABLE log_master IS 'Tracks ingestion of each log file or log batch';


-- ===========================================================
-- 2) log_event (parsed log events)
-- ===========================================================
CREATE TABLE IF NOT EXISTS log_event (
    id               BIGSERIAL PRIMARY KEY,

    -- Relationship to log_master
    master_id        BIGINT NOT NULL REFERENCES log_master(id) ON DELETE CASCADE,

    -- Core parsed fields
    ts               TIMESTAMPTZ,             -- parsed timestamp (nullable)
    level            TEXT,                    -- INFO / WARN / ERROR / DEBUG
    logger_name      TEXT,                    -- class/module/category
    thread_name      TEXT,                    -- thread id / name
    service_name     TEXT,                    -- duplicated from master for fast filtering

    -- Message & original content
    message          TEXT NOT NULL,           -- cleaned message
    raw_line         TEXT,                    -- original raw line (optional)

    -- Exception / error handling
    exception_type   TEXT,                    -- e.g. java.lang.NullPointerException
    exception_msg    TEXT,
    stack_trace      TEXT,                    -- multi-line if present

    -- Observability IDs (OTEL)
    trace_id         TEXT,
    span_id          TEXT,

    -- Embedding vector (semantic representation)
    embedding        VECTOR(384),            -- adjust if using different model dims

    metadata         JSONB,                   -- flexible metadata

    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE log_event IS 'Contains parsed log lines/events with optional embedding vectors';


-- ===========================================================
-- 3) Indexes for log_event
-- ===========================================================

-- Fast lookup by ingest + timestamp
CREATE INDEX IF NOT EXISTS idx_log_event_master_ts
    ON log_event (master_id, ts);

-- Fast filtering by service + log level
CREATE INDEX IF NOT EXISTS idx_log_event_service_level
    ON log_event (service_name, level);

-- JSON search performance
CREATE INDEX IF NOT EXISTS idx_log_event_metadata_gin
    ON log_event USING GIN (metadata);

-- HNSW vector index for semantic search
CREATE INDEX IF NOT EXISTS idx_log_event_embedding_hnsw
    ON log_event USING hnsw (embedding vector_cosine_ops);

-- End of file
