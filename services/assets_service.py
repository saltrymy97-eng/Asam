# services/assets_service.py – منطق الأصول الثابتة والإهلاكات
import sqlite3
from datetime import date, datetime
from database import get_connection
from services.audit_service import log_action

def create_assets_tables():
    """إنشاء جداول الأصول الثابتة والإهلاكات إذا لم تكن موجودة"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fixed_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'أثاث ومعدات',
            purchase_date TEXT NOT NULL,
            purchase_cost REAL NOT NULL,
            salvage_value REAL DEFAULT 0,
            useful_life_years INTEGER DEFAULT 5,
            depreciation_method TEXT DEFAULT 'قسط ثابت',
            monthly_depreciation REAL DEFAULT 0,
            accumulated_depreciation REAL DEFAULT 0,
            book_value REAL DEFAULT 0,
            status TEXT DEFAULT 'نشط',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS depreciation_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER,
            entry_date TEXT NOT NULL,
            amount REAL NOT NULL,
            journal_entry_id INTEGER,
            notes TEXT,
            FOREIGN KEY (asset_id) REFERENCES fixed_assets(id)
        )
    """)
    conn.commit()
    conn.close()

# ========== دوال الأصول الثابتة ==========

def add_asset(name, category, purchase_date, purchase_cost, salvage_value=0, useful_life_years=5, method="قسط ثابت", notes=""):
    """إضافة أصل ثابت جديد مع حساب الإهلاك الشهري تلقائياً"""
    # حساب الإهلاك الشهري (قسط ثابت)
    depreciable_amount = purchase_cost - salvage_value
    total_months = useful_life_years * 12
    monthly_dep = round(depreciable_amount / total_months, 2) if total_months > 0 else 0

    conn = get_connection()
    conn.execute(
        """INSERT INTO fixed_assets (name, category, purchase_date, purchase_cost, salvage_value,
           useful_life_years, depreciation_method, monthly_depreciation, book_value, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, category, purchase_date, purchase_cost, salvage_value, useful_life_years, method, monthly_dep, purchase_cost, notes)
    )
    conn.commit()
    conn.close()
    return True

def get_all_assets():
    """جلب جميع الأصول الثابتة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    assets = conn.execute("SELECT * FROM fixed_assets ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(a) for a in assets]

def run_depreciation(asset_id, entry_date=None, notes=""):
    """تشغيل إهلاك شهري لأصل محدد وتسجيل قيد محاسبي"""
    if entry_date is None:
        entry_date = date.today().strftime("%Y-%m-%d")

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    asset = conn.execute("SELECT * FROM fixed_assets WHERE id=?", (asset_id,)).fetchone()
    if not asset or asset["status"] != "نشط":
        conn.close()
        return False, "الأصل غير موجود أو غير نشط"

    monthly_dep = asset["monthly_depreciation"]
    if monthly_dep <= 0:
        conn.close()
        return False, "قيمة الإهلاك صفر"

    # تسجيل قيد الإهلاك في journal_entries (مع reference فريد)
    desc = f"إهلاك {asset['name']} - {entry_date}"
    reference = f"إهلاك أصل #{asset_id} - {entry_date}"
    cur = conn.execute(
        "INSERT INTO journal_entries (date, description, reference) VALUES (?, ?, ?)",
        (entry_date, desc, reference)
    )
    entry_id = cur.lastrowid

    # مدين: مصروف الإهلاك
    conn.execute(
        "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, 'مصروف الإهلاك', ?, 0)",
        (entry_id, monthly_dep)
    )
    # دائن: مجمع الإهلاك
    conn.execute(
        "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, 'مجمع الإهلاك', 0, ?)",
        (entry_id, monthly_dep)
    )

    # تحديث الأصل
    new_accumulated = round(asset["accumulated_depreciation"] + monthly_dep, 2)
    new_book_value = round(asset["purchase_cost"] - new_accumulated, 2)
    new_status = "نشط" if new_book_value > asset["salvage_value"] else "مستنفذ"

    conn.execute(
        "UPDATE fixed_assets SET accumulated_depreciation=?, book_value=?, status=? WHERE id=?",
        (new_accumulated, new_book_value, new_status, asset_id)
    )

    # تسجيل في سجل الإهلاك
    conn.execute(
        "INSERT INTO depreciation_entries (asset_id, entry_date, amount, journal_entry_id, notes) VALUES (?, ?, ?, ?, ?)",
        (asset_id, entry_date, monthly_dep, entry_id, notes)
    )

    conn.commit()
    conn.close()
    return True, f"تم تسجيل إهلاك {monthly_dep:.2f} للأصل {asset['name']}"

def run_all_depreciations():
    """تشغيل الإهلاك الشهري لجميع الأصول النشطة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    active_assets = conn.execute("SELECT id FROM fixed_assets WHERE status='نشط' AND monthly_depreciation > 0").fetchall()
    conn.close()

    results = []
    for asset in active_assets:
        success, msg = run_depreciation(asset["id"])
        results.append((asset["id"], success, msg))
    return results

def get_depreciation_history(asset_id=None):
    """سجل الإهلاكات"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    if asset_id:
        rows = conn.execute(
            "SELECT d.*, a.name as asset_name FROM depreciation_entries d JOIN fixed_assets a ON d.asset_id = a.id WHERE d.asset_id=? ORDER BY d.entry_date DESC",
            (asset_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT d.*, a.name as asset_name FROM depreciation_entries d JOIN fixed_assets a ON d.asset_id = a.id ORDER BY d.entry_date DESC LIMIT 50"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_assets_summary():
    """ملخص الأصول الثابتة"""
    conn = get_connection()
    total_count = conn.execute("SELECT COUNT(*) FROM fixed_assets").fetchone()[0]
    total_cost = conn.execute("SELECT COALESCE(SUM(purchase_cost),0) FROM fixed_assets").fetchone()[0]
    total_dep = conn.execute("SELECT COALESCE(SUM(accumulated_depreciation),0) FROM fixed_assets").fetchone()[0]
    total_book = conn.execute("SELECT COALESCE(SUM(book_value),0) FROM fixed_assets").fetchone()[0]
    active_count = conn.execute("SELECT COUNT(*) FROM fixed_assets WHERE status='نشط'").fetchone()[0]
    conn.close()
    return {
        "total_count": total_count,
        "total_cost": total_cost,
        "total_depreciation": total_dep,
        "total_book_value": total_book,
        "active_count": active_count
    }
