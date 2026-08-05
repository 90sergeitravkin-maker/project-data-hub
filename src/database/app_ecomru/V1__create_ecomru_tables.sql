CREATE SCHEMA IF NOT EXISTS app_ecomru;

CREATE TABLE app_ecomru.processing_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity VARCHAR(255) NOT NULL,
    period VARCHAR(50),
    updated_at VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    result_path TEXT,
    error TEXT,
    meta JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_processing_groups_status ON app_ecomru.processing_groups(status);
CREATE INDEX idx_processing_groups_entity ON app_ecomru.processing_groups(entity);

CREATE TABLE app_ecomru.group_files (
    id BIGSERIAL PRIMARY KEY,
    group_id UUID NOT NULL REFERENCES app_ecomru.processing_groups(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    normalized_url TEXT,
    is_duplicate BOOLEAN DEFAULT FALSE,
    local_path TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    size BIGINT,
    sha256 VARCHAR(64),
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (group_id, url)
);
CREATE INDEX idx_group_files_status ON app_ecomru.group_files(status);

CREATE TABLE app_ecomru.downloaded_files (
    id BIGSERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    normalized_url TEXT,
    dest_path TEXT NOT NULL,
    size BIGINT,
    sha256 VARCHAR(64),
    file_type VARCHAR(50),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    downloaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    validated_at TIMESTAMP WITH TIME ZONE,
    error TEXT,
    UNIQUE (url, dest_path)
);
CREATE INDEX idx_downloaded_files_status ON app_ecomru.downloaded_files(status);