-- Увімкнення зовнішніх ключів
PRAGMA foreign_keys = ON;

-- Таблиця користувачів
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    is_active INTEGER NOT NULL DEFAULT 1
);

-- Таблиця налаштувань користувачів
CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    timezone TEXT NOT NULL DEFAULT 'Europe/Kyiv',
    morning_report_time TEXT NOT NULL DEFAULT '07:00',
    sort_order TEXT NOT NULL DEFAULT 'priority_desc,due_at_asc',
    date_format TEXT NOT NULL DEFAULT '%d.%m.%Y',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Таблиця завдань
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'personal',
    status TEXT NOT NULL DEFAULT 'in_progress',
    priority TEXT NOT NULL DEFAULT 'normal',
    due_at TEXT,
    due_date TEXT,
    recurrence_rule_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (recurrence_rule_id) REFERENCES recurrence_rules(id) ON DELETE SET NULL,
    CHECK (category IN ('personal', 'work')),
    CHECK (status IN ('in_progress', 'completed', 'cancelled')),
    CHECK (priority IN ('low', 'normal', 'high')),
    CHECK (due_at IS NULL OR due_date IS NULL)
);

-- Таблиця правил повторення (з підтримкою інтервалів у днях, місяцях, роках)
CREATE TABLE IF NOT EXISTS recurrence_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_type TEXT NOT NULL,
    interval_days INTEGER,
    interval_months INTEGER,
    interval_years INTEGER,
    days_of_week TEXT,
    day_of_month INTEGER,
    execution_time TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (rule_type IN ('daily', 'every_n_days', 'weekly', 'specific_days', 'monthly', 'every_n_months', 'yearly')),
    CHECK (interval_days IS NULL OR interval_days > 0),
    CHECK (interval_months IS NULL OR interval_months > 0),
    CHECK (interval_years IS NULL OR interval_years > 0),
    CHECK (day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 31))
);

-- Таблиця логів звітів
CREATE TABLE IF NOT EXISTS report_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    report_date TEXT NOT NULL,
    attempt_time TEXT NOT NULL DEFAULT (datetime('now')),
    status TEXT NOT NULL,
    success_time TEXT,
    error_message TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
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
