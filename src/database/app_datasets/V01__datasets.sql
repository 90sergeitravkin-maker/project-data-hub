-- 0. Создание схемы (бесконфликтно)
CREATE SCHEMA IF NOT EXISTS app_datasets;

-- 1. Создание таблицы (бесконфликтно)
CREATE TABLE IF NOT EXISTS app_datasets.datasets (
    id            BIGSERIAL PRIMARY KEY,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_active     BOOLEAN DEFAULT TRUE NOT NULL,

    source_name   VARCHAR(255) NOT NULL,
    count_rows    INTEGER NOT NULL,
    type          VARCHAR(255) NOT NULL,
    period        INTEGER,
    reporter_code VARCHAR(255)
);

-- 2. Индекс (бесконфликтно)
CREATE INDEX IF NOT EXISTS idx_datasets_source_name
    ON app_datasets.datasets(source_name);

-- 3. Функция для автообновления updated_at (бесконфликтно через OR REPLACE)
CREATE OR REPLACE FUNCTION fn_update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 4. Триггер (бесконфликтно через OR REPLACE, доступно с PG 14+)
CREATE OR REPLACE TRIGGER trg_datasets_updated_at
    BEFORE UPDATE ON app_datasets.datasets
    FOR EACH ROW
    EXECUTE FUNCTION fn_update_timestamp();