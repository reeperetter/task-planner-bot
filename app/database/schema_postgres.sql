-- Увімкнення зовнішніх ключів (в PostgreSQL вони працюють за замовчуванням, але це good practice)

-- Таблиця користувачів
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER NOT NULL DEFAULT 1
);

-- Таблиця налаштувань користувачів
CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    timezone TEXT NOT NULL DEFAULT 'Europe/Kyiv',
    morning_report_time TEXT NOT NULL DEFAULT '07:00',
    sort_order TEXT NOT NULL DEFAULT 'priority_desc,due_at_asc',
    date_format TEXT NOT NULL DEFAULT '%d.%m.%Y'
);

-- Таблиця завдань
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'personal',
    status TEXT NOT NULL DEFAULT 'in_progress',
    priority TEXT NOT NULL DEFAULT 'normal',
    due_at TIMESTAMP,
    due_date DATE,
    recurrence_rule_id INTEGER REFERENCES recurrence_rules(id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    CHECK (category IN ('personal', 'work')),
    CHECK (status IN ('in_progress', 'completed', 'cancelled')),
    CHECK (priority IN ('low', 'normal', 'high'))
);

-- Таблиця правил повторення
CREATE TABLE IF NOT EXISTS recurrence_rules (
    id SERIAL PRIMARY KEY,
    rule_type TEXT NOT NULL,
    interval_days INTEGER,
    interval_months INTEGER,
    interval_years INTEGER,
    days_of_week TEXT,
    day_of_month INTEGER,
    execution_time TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (rule_type IN ('daily', 'every_n_days', 'weekly', 'specific_days', 'monthly', 'every_n_months', 'yearly')),
    CHECK (interval_days IS NULL OR interval_days > 0),
    CHECK (interval_months IS NULL OR interval_months > 0),
    CHECK (interval_years IS NULL OR interval_years > 0),
    CHECK (day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 31))
);

-- Таблиця логів звітів
CREATE TABLE IF NOT EXISTS report_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    report_date DATE NOT NULL,
    attempt_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,
    success_time TIMESTAMP,
    error_message TEXT,
    CHECK (status IN ('attempt', 'success', 'failed')),
    UNIQUE(user_id, report_date, status)
);

-- Індекси для оптимізації запитів
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due_at ON tasks(due_at);
CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);
CREATE INDEX IF NOT EXISTS idx_tasks_recurrence_rule_id ON tasks(recurrence_rule_id);
CREATE INDEX IF NOT EXISTS idx_report_log_user_date ON report_log(user_id, report_date);
