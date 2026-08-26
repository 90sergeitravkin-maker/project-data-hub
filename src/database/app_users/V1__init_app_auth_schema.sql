-- Создание схемы, если её нет
CREATE SCHEMA IF NOT EXISTS app_users;

-- Создание функции для обновления updated_at (если её ещё нет)
CREATE OR REPLACE FUNCTION app_users.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Таблица auth_users (создаётся только если отсутствует)
CREATE TABLE IF NOT EXISTS app_users.auth_users (
    id bigserial NOT NULL,
    email varchar(255) NOT NULL,
    username varchar(50) NOT NULL,
    password_hash varchar(255) NOT NULL,
    is_active bool DEFAULT true NOT NULL,
    created_at timestamptz DEFAULT now() NOT NULL,
    updated_at timestamptz DEFAULT now() NOT NULL,
    CONSTRAINT auth_users_email_key UNIQUE (email),
    CONSTRAINT auth_users_pkey PRIMARY KEY (id),
    CONSTRAINT auth_users_username_key UNIQUE (username)
);

-- Индексы для auth_users
CREATE INDEX IF NOT EXISTS idx_auth_users_email ON app_users.auth_users USING btree (email);
CREATE INDEX IF NOT EXISTS idx_auth_users_username ON app_users.auth_users USING btree (username);

-- Триггер для автоматического обновления updated_at (создаём только если не существует)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_auth_users_set_updated_at'
          AND tgrelid = 'app_users.auth_users'::regclass
    ) THEN
        CREATE TRIGGER trg_auth_users_set_updated_at
        BEFORE UPDATE ON app_users.auth_users
        FOR EACH ROW EXECUTE FUNCTION app_users.set_updated_at();
    END IF;
END
$$;

-- Права доступа для auth_users
ALTER TABLE app_users.auth_users OWNER TO postgres;
GRANT ALL ON TABLE app_users.auth_users TO postgres;

-- Таблица login_stats (создаётся только если отсутствует)
CREATE TABLE IF NOT EXISTS app_users.login_stats (
    id bigserial NOT NULL,
    user_id int8 NOT NULL,
    login_at timestamptz DEFAULT now() NOT NULL,
    ip_address inet NULL,
    user_agent text NOT NULL,
    success bool NOT NULL,
    failure_reason varchar(100) NULL,
    session_id uuid NOT NULL,
    CONSTRAINT login_stats_pkey PRIMARY KEY (id),
    CONSTRAINT login_stats_user_id_fkey FOREIGN KEY (user_id) REFERENCES app_users.auth_users(id) ON DELETE CASCADE
);

-- Индексы для login_stats
CREATE INDEX IF NOT EXISTS idx_login_stats_login_at ON app_users.login_stats USING btree (login_at);
CREATE INDEX IF NOT EXISTS idx_login_stats_success ON app_users.login_stats USING btree (success);
CREATE INDEX IF NOT EXISTS idx_login_stats_user_id ON app_users.login_stats USING btree (user_id);

-- Права доступа для login_stats
ALTER TABLE app_users.login_stats OWNER TO postgres;
GRANT ALL ON TABLE app_users.login_stats TO postgres;