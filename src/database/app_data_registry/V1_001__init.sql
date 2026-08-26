-- src/database/migrations/V1__init_auth.sql
-- Flyway migration: создание таблиц аутентификации и статистики входов
-- PostgreSQL 15 compatible | Alembic не используется

CREATE SCHEMA IF NOT EXISTS app_auth;

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS app_auth.auth_users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Явное указание схемы app_auth для индексов
CREATE INDEX IF NOT EXISTS idx_auth_users_email ON app_auth.auth_users(email);
CREATE INDEX IF NOT EXISTS idx_auth_users_username ON app_auth.auth_users(username);

-- Таблица статистики входов
-- Исправлено: неверный синтаксис 'auth_users.login_stats' → 'app_auth.login_stats'
CREATE TABLE IF NOT EXISTS app_auth.login_stats (
    id BIGSERIAL PRIMARY KEY,
    -- Исправлено: убран конфликт NOT NULL + ON DELETE SET NULL → заменено на ON DELETE CASCADE
    user_id BIGINT NOT NULL REFERENCES app_auth.auth_users(id) ON DELETE CASCADE,
    login_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT,
    success BOOLEAN NOT NULL,
    failure_reason VARCHAR(100),
    session_id UUID DEFAULT gen_random_uuid()
);

CREATE INDEX IF NOT EXISTS idx_login_stats_user_id ON app_auth.login_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_login_stats_login_at ON app_auth.login_stats(login_at DESC);
CREATE INDEX IF NOT EXISTS idx_login_stats_success ON app_auth.login_stats(success);

-- Функция и триггер для автообновления updated_at
CREATE OR REPLACE FUNCTION app_auth.fn_update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Явное указание схемы в DROP/CREATE TRIGGER и EXECUTE FUNCTION
DROP TRIGGER IF EXISTS trg_update_users ON app_auth.auth_users;
CREATE TRIGGER trg_update_users
    BEFORE UPDATE ON app_auth.auth_users
    FOR EACH ROW
    EXECUTE FUNCTION app_auth.fn_update_timestamp();