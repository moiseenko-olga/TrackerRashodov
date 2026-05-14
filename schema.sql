-- ============================================================
--  ТРЕКЕР РАСХОДОВ — Схема базы данных SQLite
-- ============================================================

-- Таблица категорий 
CREATE TABLE IF NOT EXISTS categories (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT    NOT NULL UNIQUE,
    color  TEXT    NOT NULL DEFAULT '#888888'
);

-- Таблица расходов 
CREATE TABLE IF NOT EXISTS expenses (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    amount         REAL    NOT NULL CHECK(amount > 0),
    category_id    INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    description    TEXT    NOT NULL DEFAULT '',
    date           TEXT    NOT NULL,            -- YYYY-MM-DD
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Таблица лимитов
CREATE TABLE IF NOT EXISTS limits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL UNIQUE REFERENCES categories(id) ON DELETE CASCADE,
    monthly_lim REAL    NOT NULL CHECK(monthly_lim > 0)
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id);

-- ============================================================
--  ЗАПРОС 1: Все расходы за текущий месяц
-- ============================================================
SELECT
    e.id,
    e.amount,
    c.name          AS category,
    e.description,
    e.date
FROM expenses e
JOIN categories c ON c.id = e.category_id
WHERE strftime('%Y-%m', e.date) = strftime('%Y-%m', 'now')
ORDER BY e.date DESC, e.id DESC;

-- ============================================================
--  ЗАПРОС 2: Сумма расходов по категориям за месяц
-- ============================================================
SELECT
    c.name              AS category,
    c.color,
    SUM(e.amount)       AS total_spent,
    COUNT(e.id)         AS transactions
FROM expenses e
JOIN categories c ON c.id = e.category_id
WHERE strftime('%Y-%m', e.date) = strftime('%Y-%m', 'now')
GROUP BY c.id
ORDER BY total_spent DESC;

-- ============================================================
--  ЗАПРОС 3: История расходов по месяцам (последние 6)
-- ============================================================
SELECT
    strftime('%Y-%m', date)  AS month,
    SUM(amount)              AS total,
    COUNT(*)                 AS count
FROM expenses
GROUP BY month
ORDER BY month DESC
LIMIT 6;

-- ============================================================
--  ЗАПРОС 4: Категории, превысившие 20% лимита
-- ============================================================
SELECT
    c.name,
    SUM(e.amount)                               AS spent,
    l.monthly_lim,
    ROUND(SUM(e.amount) / l.monthly_lim * 100)  AS pct_used
FROM expenses e
JOIN categories c ON c.id = e.category_id
JOIN limits     l ON l.category_id = c.id
WHERE strftime('%Y-%m', e.date) = strftime('%Y-%m', 'now')
GROUP BY c.id
HAVING spent >= l.monthly_lim * 0.2
ORDER BY pct_used DESC;

-- ============================================================
--  ЗАПРОС 5: Топ-3 самых дорогих транзакции месяца
-- ============================================================
SELECT
    e.amount,
    c.name   AS category,
    e.description,
    e.date
FROM expenses e
JOIN categories c ON c.id = e.category_id
WHERE strftime('%Y-%m', e.date) = strftime('%Y-%m', 'now')
ORDER BY e.amount DESC
LIMIT 3;