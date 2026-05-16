"""
Трекер расходов — Flask Web App
Запуск: python app.py  →  откроется браузер на http://127.0.0.1:5000
"""

import sqlite3
import datetime
import os
import sys
import threading
import webbrowser
from flask import Flask, render_template, request, jsonify, redirect, url_for

base = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(base, 'templates'))

# ─── ПУТЬ К БД (работает и как .py, и как .exe) ───────────────────────────────
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

DB_FILE = os.path.join(get_base_dir(), "expenses.db")

CATEGORIES = [
    ("☕ Кофе",        "#7C6AF5", 2000),
    ("🍕 Еда",         "#22C88A", 15000),
    ("🚌 Транспорт",   "#F5A623", 5000),
    ("🎬 Развлечения", "#E84E4E", 8000),
    ("🏠 Жильё",       "#4B8BF5", 20000),
    ("📱 Связь",       "#00BCD4", 2000),
    ("💊 Здоровье",    "#FF7043", 5000),
    ("👗 Одежда",      "#AB47BC", 10000),
    ("📚 Образование", "#26A69A", 5000),
    ("🛒 Другое",      "#78909C", 5000),
]

MONTHS_RU = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
             "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]

# ─── DATABASE ──────────────────────────────────────────────────────────────────
def get_db():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS categories (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        name  TEXT NOT NULL UNIQUE,
        color TEXT NOT NULL DEFAULT '#888888'
    );

    CREATE TABLE IF NOT EXISTS expenses (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        amount      REAL NOT NULL CHECK(amount > 0),
        category_id INTEGER NOT NULL REFERENCES categories(id),
        description TEXT NOT NULL DEFAULT '',
        date        TEXT NOT NULL,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS limits (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL UNIQUE REFERENCES categories(id),
        monthly_lim REAL NOT NULL CHECK(monthly_lim > 0)
    );

    CREATE INDEX IF NOT EXISTS idx_expenses_date
    ON expenses(date);

    CREATE INDEX IF NOT EXISTS idx_expenses_category
    ON expenses(category_id);

    """)
    for name, color, default_lim in CATEGORIES:
        cur.execute("INSERT OR IGNORE INTO categories(name, color) VALUES(?,?)", (name, color))
        cur.execute("""INSERT OR IGNORE INTO limits(category_id, monthly_lim)
                       SELECT id, ? FROM categories WHERE name=?""", (default_lim, name))

    cur.execute("SELECT COUNT(*) FROM expenses")
    if cur.fetchone()[0] == 0:
        today = datetime.date.today()
        m = today.strftime("%Y-%m")
        demo = [
            (320,  "☕ Кофе",        "Латте в Surf Coffee",        m+"-03"),
            (180,  "☕ Кофе",        "Американо у метро",           m+"-05"),
            (250,  "☕ Кофе",        "Флэт-уайт",                  m+"-07"),
            (560,  "☕ Кофе",        "Обед-кофе-кофе",             m+"-10"),
            (890,  "🍕 Еда",         "Пицца с коллегами",          m+"-04"),
            (1200, "🍕 Еда",         "Продукты в магазине",         m+"-08"),
            (450,  "🚌 Транспорт",   "Такси домой",                m+"-06"),
            (2400, "🎬 Развлечения", "Кино + ресторан",            m+"-09"),
            (3500, "🏠 Жильё",       "Коммунальные услуги",        m+"-01"),
            (800,  "📱 Связь",       "Мобильный интернет",         m+"-02"),
            (1500, "💊 Здоровье",    "Аптека",                     m+"-11"),
            (4200, "👗 Одежда",      "Новые кроссовки",            m+"-12"),
        ]
        for amount, cat, desc, date in demo:
            cur.execute("""INSERT INTO expenses(amount, category_id, description, date)
                           SELECT ?, id, ?, ? FROM categories WHERE name=?""",
                        (amount, desc, date, cat))
    conn.commit()
    conn.close()

# ─── API HELPERS ───────────────────────────────────────────────────────────────
def get_month_expenses(year, month):
    prefix = f"{year}-{month:02d}"
    with get_db() as conn:
        return conn.execute("""
            SELECT e.id, e.amount, c.name, c.color, e.description, e.date
            FROM expenses e JOIN categories c ON c.id = e.category_id
            WHERE e.date LIKE ? ORDER BY e.date DESC, e.id DESC
        """, (prefix+"%",)).fetchall()

def get_category_totals(year, month):
    prefix = f"{year}-{month:02d}"
    with get_db() as conn:
        return conn.execute("""
            SELECT c.name, c.color, SUM(e.amount) as total
            FROM expenses e JOIN categories c ON c.id = e.category_id
            WHERE e.date LIKE ? GROUP BY c.id ORDER BY total DESC
        """, (prefix+"%",)).fetchall()

def get_monthly_total(year, month):
    prefix = f"{year}-{month:02d}"
    with get_db() as conn:
        return conn.execute("SELECT COALESCE(SUM(amount),0) FROM expenses WHERE date LIKE ?",
                            (prefix+"%",)).fetchone()[0]

def get_limits():
    with get_db() as conn:
        return dict(conn.execute(
            "SELECT c.name, l.monthly_lim FROM limits l JOIN categories c ON c.id=l.category_id"
        ).fetchall())

def get_monthly_history():
    with get_db() as conn:
        return conn.execute("""
            SELECT strftime('%Y-%m', date) as month, SUM(amount), COUNT(*)
            FROM expenses GROUP BY month ORDER BY month DESC LIMIT 6
        """).fetchall()

def get_over_limit(year, month):
    prefix = f"{year}-{month:02d}"
    with get_db() as conn:
        return conn.execute("""
            SELECT c.name, SUM(e.amount), l.monthly_lim,
                   ROUND(SUM(e.amount)/l.monthly_lim*100) as pct
            FROM expenses e JOIN categories c ON c.id=e.category_id
            JOIN limits l ON l.category_id=c.id
            WHERE e.date LIKE ? GROUP BY c.id HAVING SUM(e.amount) >= l.monthly_lim*0.8
            ORDER BY pct DESC
        """, (prefix+"%",)).fetchall()

# ─── ROUTES ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    today = datetime.date.today()
    return redirect(url_for("dashboard", year=today.year, month=today.month))

@app.route("/dashboard")
def dashboard():
    today = datetime.date.today()
    year  = int(request.args.get("year",  today.year))
    month = int(request.args.get("month", today.month))
    total = get_monthly_total(year, month)
    cats  = get_category_totals(year, month)
    limits = get_limits()
    total_limit = sum(limits.values())
    expenses_count = len(get_month_expenses(year, month))
    over = get_over_limit(year, month)
    return render_template("dashboard.html",
        year=year, month=month, month_name=MONTHS_RU[month],
        total=total, cats=cats, limits=limits,
        total_limit=total_limit, expenses_count=expenses_count,
        over_limit=over, months_ru=MONTHS_RU)

@app.route("/expenses")
def expenses():
    today = datetime.date.today()
    year  = int(request.args.get("year",  today.year))
    month = int(request.args.get("month", today.month))
    rows  = get_month_expenses(year, month)
    return render_template("expenses.html",
        year=year, month=month, month_name=MONTHS_RU[month],
        rows=rows, months_ru=MONTHS_RU)

@app.route("/add", methods=["GET", "POST"])
def add():
    today = datetime.date.today()
    msg = None
    if request.method == "POST":
        try:
            amount = float(request.form["amount"].replace(",", ".").replace(" ", ""))
            if amount <= 0: raise ValueError
            cat  = request.form["category"]
            desc = request.form.get("description", "")
            date = request.form["date"]
            datetime.date.fromisoformat(date)
            with get_db() as conn:
                conn.execute("""INSERT INTO expenses(amount, category_id, description, date)
                                SELECT ?, id, ?, ? FROM categories WHERE name=?""",
                             (amount, desc, date, cat))
            msg = ("ok", f"✅ Расход {amount:,.0f} ₽ добавлен!")
        except Exception:
            msg = ("err", "❌ Ошибка: проверьте введённые данные.")
    cat_names = [c[0] for c in CATEGORIES]
    return render_template("add.html", categories=cat_names,
                           today=today.isoformat(), msg=msg, months_ru=MONTHS_RU)

@app.route("/report")
def report():
    today = datetime.date.today()
    year  = int(request.args.get("year",  today.year))
    month = int(request.args.get("month", today.month))
    total = get_monthly_total(year, month)
    cats  = get_category_totals(year, month)
    limits = get_limits()
    history = get_monthly_history()
    expenses_count = len(get_month_expenses(year, month))
    return render_template("report.html",
        year=year, month=month, month_name=MONTHS_RU[month],
        total=total, cats=cats, limits=limits,
        expenses_count=expenses_count, history=history,
        months_ru=MONTHS_RU)

@app.route("/notifications")
def notifications():
    today = datetime.date.today()
    year  = int(request.args.get("year",  today.year))
    month = int(request.args.get("month", today.month))
    rows  = get_month_expenses(year, month)
    limits = get_limits()
    cats = {}
    for _, amount, cat, color, *_ in rows:
        cats[cat] = cats.get(cat, 0) + amount
    total = sum(cats.values())
    notifs = []
    coffee = cats.get("☕ Кофе", 0)
    food   = cats.get("🍕 Еда", 0)
    coffee_lim = limits.get("☕ Кофе", 2000)
    if coffee > coffee_lim * 0.5:
        cups = int(coffee / 160)
        notifs.append(("warn", "☕", "Привет, кофеман!",
            f"Тратишь слишком много на кофе. Уже {coffee:,.0f} ₽ — это примерно {cups} стаканов. Лимит: {coffee_lim:,.0f} ₽."))
    over_limit = get_over_limit(year, month)
    for name, spent, lim, pct in over_limit:
        if pct >= 100:
            notifs.append(("danger", "🚨", f"Лимит по «{name}» превышен!",
                f"Потрачено {spent:,.0f} ₽ при лимите {lim:,.0f} ₽ ({int(pct)}%). Пора притормозить."))
        elif name != "☕ Кофе":
            notifs.append(("warn", "⚠️", f"«{name}» — уже {int(pct)}% лимита",
                f"Осталось всего {lim-spent:,.0f} ₽. Будь осторожен с расходами."))
    if food > 0 and coffee / (food or 1) > 0.3:
        notifs.append(("warn", "😅", "Кофе vs еда",
            f"Кофе = {int(coffee/food*100)}% от трат на еду. Это много. Может, заварить дома?"))
    if cats:
        top_cat, top_amt = max(cats.items(), key=lambda x: x[1])
        if total and top_amt / total > 0.5:
            notifs.append(("warn", "📊", f"«{top_cat}» — главная статья расходов",
                f"Забирает {int(top_amt/total*100)}% всего бюджета месяца."))
    day = today.day
    if day <= 10 and total > sum(limits.values()) * 0.4:
        notifs.append(("warn", "📅", "Ранний старт!",
            f"Только {day}-й день месяца, а уже потрачено {total:,.0f} ₽."))
    if not notifs:
        notifs.append(("ok", "🎉", "Всё под контролем!", "Расходы в норме, лимиты соблюдаются. Так держать!"))
    return render_template("notifications.html",
        year=year, month=month, month_name=MONTHS_RU[month],
        notifs=notifs, months_ru=MONTHS_RU)

@app.route("/limits", methods=["GET", "POST"])
def limits_page():
    today = datetime.date.today()
    year  = int(request.args.get("year",  today.year))
    month = int(request.args.get("month", today.month))
    msg = None
    if request.method == "POST":
        cat_name = request.form["category"]
        try:
            val = float(request.form["limit"].replace(",", ".").replace(" ", ""))
            if val <= 0: raise ValueError
            with get_db() as conn:
                conn.execute("""UPDATE limits SET monthly_lim=?
                                WHERE category_id=(SELECT id FROM categories WHERE name=?)""",
                             (val, cat_name))
            msg = ("ok", f"✅ Лимит для «{cat_name}» обновлён!")
        except Exception:
            msg = ("err", "❌ Введите положительное число.")
    limits = get_limits()
    cats   = {name: amt for name, _, amt in get_category_totals(year, month)}
    data   = []
    for name, color, _ in CATEGORIES:
        lim   = limits.get(name, 5000)
        spent = cats.get(name, 0)
        pct   = min(int(spent / lim * 100), 100) if lim else 0
        data.append({"name": name, "color": color, "lim": lim, "spent": spent, "pct": pct})
    return render_template("limits.html",
        year=year, month=month, month_name=MONTHS_RU[month],
        data=data, msg=msg, months_ru=MONTHS_RU)

# ─── JSON API ──────────────────────────────────────────────────────────────────
@app.route("/api/delete/<int:eid>", methods=["POST"])
def api_delete(eid):
    with get_db() as conn:
        conn.execute("DELETE FROM expenses WHERE id=?", (eid,))
    return jsonify({"ok": True})

@app.route("/api/delete_all", methods=["POST"])
def api_delete_all():
    with get_db() as conn:
        conn.execute("DELETE FROM expenses")
    return jsonify({"ok": True})

# ─── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    print("✅ Трекер расходов запущен: http://127.0.0.1:5000")
    app.run(debug=False, port=5000)
