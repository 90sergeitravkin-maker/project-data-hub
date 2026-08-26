CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS app_text_dup_check;

CREATE TABLE IF NOT EXISTS app_text_dup_check.texts (
    id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code    VARCHAR(50) NOT NULL,
    content TEXT        NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_texts_code ON app_text_dup_check.texts (code);
CREATE INDEX IF NOT EXISTS ix_texts_content ON app_text_dup_check.texts (content);