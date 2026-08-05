-- Flyway migration: V4__create_mail_tables.sql
-- PostgreSQL 15 compatible
-- Соответствует модели: src/back/app_mail/models.py → MailTask

-- 1. Создание схемы (бесконфликтно)
CREATE SCHEMA IF NOT EXISTS app_mail;

-- 2. Таблица mail_tasks (ровно те колонки, что в модели MailTask)
CREATE TABLE IF NOT EXISTS app_mail.mail_tasks (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id         UUID NOT NULL DEFAULT gen_random_uuid(),
    to_email        VARCHAR(255) NOT NULL,
    subject         VARCHAR(255) NOT NULL,
    body_preview    TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    sent_at         TIMESTAMPTZ,
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Индексы (соответствуют index=True в модели)
CREATE UNIQUE INDEX IF NOT EXISTS uq_mail_tasks_task_id
    ON app_mail.mail_tasks (task_id);

CREATE INDEX IF NOT EXISTS ix_mail_tasks_to_email
    ON app_mail.mail_tasks (to_email);

CREATE INDEX IF NOT EXISTS ix_mail_tasks_status
    ON app_mail.mail_tasks (status);

-- 4. Комментарии (опционально, для документации)
COMMENT ON TABLE app_mail.mail_tasks IS 'Реестр задач отправки email-уведомлений';
COMMENT ON COLUMN app_mail.mail_tasks.task_id IS 'UUID задачи (уникальный)';
COMMENT ON COLUMN app_mail.mail_tasks.status IS 'pending | sending | sent | failed';