-- Enable UUID extension for unique artifact IDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Artifacts Table (Model Checkpoint Catalog)
CREATE TABLE IF NOT EXISTS artifacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL DEFAULT 'v1.0.0',
    total_bytes BIGINT NOT NULL,
    sha256_hash CHAR(64) NOT NULL,
    tensor_dtype VARCHAR(20) NOT NULL DEFAULT 'float32',
    status VARCHAR(20) NOT NULL DEFAULT 'UPLOADING' CHECK (status IN ('UPLOADING', 'COMMITTED', 'CORRUPTED')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_name_version UNIQUE (name, version)
);

-- 2. Artifact Chunks Table (The Manifest)
CREATE TABLE IF NOT EXISTS artifact_chunks (
    id SERIAL PRIMARY KEY,
    artifact_id UUID NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    byte_offset BIGINT NOT NULL,
    byte_length BIGINT NOT NULL,
    chunk_hash CHAR(64) NOT NULL,
    storage_path VARCHAR(512) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_artifact_chunk UNIQUE (artifact_id, chunk_index)
);

-- Index for instant chunk deduplication lookups
CREATE INDEX IF NOT EXISTS idx_chunks_hash ON artifact_chunks(chunk_hash);

-- 3. Access Telemetry Table (Analytics & Diagnostics Log)
CREATE TABLE IF NOT EXISTS access_telemetry (
    id BIGSERIAL PRIMARY KEY,
    client_ip VARCHAR(45) NOT NULL,
    artifact_id UUID REFERENCES artifacts(id) ON DELETE SET NULL,
    chunk_hash CHAR(64) NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('READ', 'WRITE')),
    response_time_ms DOUBLE PRECISION NOT NULL,
    cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    bytes_transferred BIGINT NOT NULL DEFAULT 0,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for lightning-fast analytics queries
CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON access_telemetry(timestamp);
CREATE INDEX IF NOT EXISTS idx_telemetry_cache_hit ON access_telemetry(cache_hit);
CREATE INDEX IF NOT EXISTS idx_telemetry_artifact ON access_telemetry(artifact_id);