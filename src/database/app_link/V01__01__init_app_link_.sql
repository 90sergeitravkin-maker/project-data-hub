-- Создаём схему, если не существует
CREATE SCHEMA IF NOT EXISTS app_link;

-- Таблица для хранения ссылок (дедупликация)
CREATE TABLE IF NOT EXISTS app_link.links (
     id             SERIAL      PRIMARY                key
    ,created_at     timestamptz DEFAULT now() NOT NULL
    ,updated_at     timestamptz DEFAULT now() NOT NULL
    ,is_active      bool        DEFAULT true  NOT null
    ,url            TEXT                      NOT NULL
    ,url_normalized TEXT                      NOT NULL
    ,url_hash       TEXT                      NOT NULL UNIQUE
);

-- Индекс для быстрого поиска по URL (важен для операций ANY и ON CONFLICT)
CREATE INDEX IF NOT EXISTS idx_links_url ON app_link.links (url);

-- Опционально: комментарии к таблице и колонкам
COMMENT ON TABLE  app_link.links            IS 'Хранит уникальные ссылки для дедупликации';
COMMENT ON COLUMN app_link.links.url        IS 'Нормализованный URL (нижний регистр, обрезан)';
COMMENT ON COLUMN app_link.links.created_at IS 'Время добавления ссылки';