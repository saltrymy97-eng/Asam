# services/assets_service.py – منطق الأصول الثابتة والإهلاكات (v2.0)
# ✅ Registry + conn=None + شراء من صندوق/بنك مع فحص الرصيد
import sqlite3
from datetime import date, datetime
from database import get_connection, close_connection
from services.audit_service import log_action
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry


def create_assets_tables(conn=None):
    """إنشاء جداول الأصول الثابتة والإهلاكات إذا لم تكن موجودة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
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
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            close_connection(conn)


# ============================================================
# إضافة أصل ثابت (مع قيد شراء اختياري)
# ============================================================
def add_asset(name, category, purchase_date, purchase_cost,
              salvage_value=0, useful_life_years=5, method="قسط ثابت",
              notes="", payment_account_code=None, payment_method="cash",
              created_by="admin", conn=None):
    """
    إضافة أصل ثابت جديد مع حساب الإهلاك الشهري تلقائياً.
    
    Args:
        payment_account_code: كود الصندوق/البنك (اختياري)
        payment_method:       'cash' | 'bank' | None (بدون شراء نقدي)
    
    Returns:
        (asset_id, None) عند النجاح
        (None, "رسالة")  عند الفشل
    """
    create_assets_tables(conn=conn)

    purchase_cost = float(purchase_cost)
    salvage_value = float(salvage_value or 0)

    if purchase_cost <= 0:
        return None, "تكلفة الشراء يجب أن تكون أكبر من صفر"

    depreciable_amount = purchase_cost - salvage_value
    total_months = max(1, useful_life_years * 12)
    monthly_dep = round(depreciable_amount / total_months, 2)

    # ✅ فحص الرصيد قبل الشراء (إذا فيه دفع)
    if payment_account_code and payment_method in ('cash', 'bank'):
        from services.cash_service import check_sufficient_balance
        ok, err = check_sufficient_balance(
            payment_account_code, purchase_cost, conn=conn
        )
        if not ok:
            return None, f"لا يمكن شراء الأصل: {err}"

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN")

        # 1. إدراج الأصل
        cur = conn.execute(
            """INSERT INTO fixed_assets 
               (name, category, purchase_date, purchase_cost, salvage_value,
                useful_life_years, depreciation_method, monthly_depreciation,
                book_value, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, category, purchase_date, purchase_cost, salvage_value,
             useful_life_years, method, monthly_dep, purchase_cost, notes)
        )
        asset_id = cur.lastrowid

        # 2. ✅ قيد الشراء (إذا فيه دفع)
        if payment_account_code and payment_method in ('cash', 'bank'):
            acc_fixed_assets = get_functional_account("fixed_assets")
            if not acc_fixed_assets:
                # fallback: نستخدم حساب الأصول الثابتة الافتراضي
                acc_fixed_assets = get_functional_account("Asset") or "1401"

            lines = [
                {
                    "account": acc_fixed_assets,
                    "debit": purchase_cost,
                    "credit": 0,
                    "currency_code": "YER",
                    "exchange_rate": 1.0,
                },
                {
                    "account": payment_account_code,
                    "debit": 0,
                    "credit": purchase_cost,
                    "currency_code": "YER",
                    "exchange_rate": 1.0,
                },
            ]

            entry_id, entry_error = save_journal_entry(
                description=f"شراء أصل ثابت: {name}",
                lines=lines,
                entry_date=purchase_date,
                conn=conn,
            )
            if entry_error:
                raise Exception(f"فشل إنشاء قيد الشراء: {entry_error}")

            # ✅ تسجيل الحركة في الصندوق/البنك
            if payment_method == 'cash':
                try:
                    from services.cash_service import add_cash_transaction
                    acc_row = conn.execute(
                        "SELECT id FROM cash_accounts WHERE account_code=? AND is_active=1 LIMIT 1",
                        (payment_account_code,)
                    ).fetchone()
                    if acc_row:
                        add_cash_transaction(
                            acc_row['id'],
                            purchase_date,
                            f"شراء أصل: {name}",
                            'withdrawal',
                            purchase_cost,
                            reference=f"asset#{asset_id}",
                            create_journal=False,
                            conn=conn,
                            skip_balance_check=True,
                        )
                except Exception as e:
                    print(f"⚠️ فشل تسجيل حركة الصندوق: {e}")
            elif payment_method == 'bank':
                try:
                    from services.bank_service import add_bank_transaction
                    acc_row = conn.execute(
                        "SELECT id FROM bank_accounts WHERE account_code=? AND is_active=1 LIMIT 1",
                        (payment_account_code,)
                    ).fetchone()
                    if acc_row:
                        add_bank_transaction(
                            acc_row['id'],
                            purchase_date,
                            f"شراء أصل: {name}",
                            'withdrawal',
                            purchase_cost,
                            reference=f"asset#{asset_id}",
                            conn=conn,
                            skip_balance_check=True,
                        )
                except Exception as e:
                    print(f"⚠️ فشل تسجيل حركة البنك: {e}")

        if own_conn:
            conn.commit()

        log_action(
            username=created_by,
            action="إضافة أصل ثابت",
            table_name="fixed_assets",
            record_id=asset_id,
            new_value=f"{name}, التكلفة: {purchase_cost:,.2f}"
        )

        return asset_id, None

    except Exception as e:
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return None, str(e)
    finally:
        if own_conn:
            close_connection(conn)


def get_all_assets(conn=None):
    """جلب جميع الأصول الثابتة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        assets = conn.execute(
            "SELECT * FROM fixed_assets ORDER BY created_at DESC"
        ).fetchall()
        return [dict(a) for a in assets]
    finally:
        if own_conn:
            close_connection(conn)


# ============================================================
# تشغيل الإهلاك الشهري
# ============================================================
def run_depreciation(asset_id, entry_date=None, notes="",
                     created_by="admin", conn=None):
    """
    تشغيل إهلاك شهري لأصل محدد.
    
    ⚠️ الإهلاك لا يمسّ الصندوق/البنك.
    """
    if entry_date is None:
        entry_date = date.today().strftime("%Y-%m-%d")

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN")

        asset = conn.execute(
            "SELECT * FROM fixed_assets WHERE id=?", (asset_id,)
        ).fetchone()
        if not asset:
            if own_conn:
                conn.rollback()
            return False, "الأصل غير موجود"
        if asset["status"] != "نشط":
            if own_conn:
                conn.rollback()
            return False, "الأصل غير نشط"

        monthly_dep = float(asset["monthly_depreciation"] or 0)
        if monthly_dep <= 0:
            if own_conn:
                conn.rollback()
            return False, "قيمة الإهلاك صفر"

        # رقم تسلسلي
        count = conn.execute(
            "SELECT COUNT(*) FROM depreciation_entries WHERE asset_id=?",
            (asset_id,)
        ).fetchone()[0] + 1

        desc = f"إهلاك {asset['name']} - الشهر {count} - {entry_date}"

        # الحسابات الوظيفية
        acc_dep_exp = get_functional_account("depreciation_expense")
        acc_accum_dep = get_functional_account("accumulated_depreciation")

        if not acc_dep_exp or not acc_accum_dep:
            raise Exception("حسابات الإهلاك الوظيفية غير معرفة")

        lines = [
            {
                "account": acc_dep_exp,
                "debit": monthly_dep,
                "credit": 0,
                "currency_code": "YER",
                "exchange_rate": 1.0,
            },
            {
                "account": acc_accum_dep,
                "debit": 0,
                "credit": monthly_dep,
                "currency_code": "YER",
                "exchange_rate": 1.0,
            },
        ]

        entry_id, entry_error = save_journal_entry(
            description=desc,
            lines=lines,
            entry_date=entry_date,
            conn=conn,
        )
        if entry_error:
            raise Exception(f"فشل إنشاء قيد الإهلاك: {entry_error}")

        # تحديث قيم الأصل
        new_accumulated = round(
            float(asset["accumulated_depreciation"] or 0) + monthly_dep, 2
        )
        new_book_value = round(
            float(asset["purchase_cost"]) - new_accumulated, 2
        )
        salvage = float(asset["salvage_value"] or 0)
        new_status = "نشط" if new_book_value > salvage else "مستنفذ"

        conn.execute(
            "UPDATE fixed_assets SET accumulated_depreciation=?, "
            "book_value=?, status=? WHERE id=?",
            (new_accumulated, new_book_value, new_status, asset_id)
        )

        conn.execute(
            "INSERT INTO depreciation_entries "
            "(asset_id, entry_date, amount, journal_entry_id, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (asset_id, entry_date, monthly_dep, entry_id, notes)
        )

        if own_conn:
            conn.commit()

        log_action(
            username=created_by,
            action="إصدار إهلاك",
            table_name="depreciation_entries",
            record_id=entry_id,
            new_value=f"الأصل: {asset['name']}, القيمة: {monthly_dep:,.2f}"
        )

        return True, f"تم تسجيل إهلاك {monthly_dep:.2f} للأصل {asset['name']} (شهر {count})"

    except Exception as e:
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False, f"فشل تسجيل الإهلاك: {str(e)}"
    finally:
        if own_conn:
            close_connection(conn)


def run_all_depreciations(conn=None):
    """تشغيل الإهلاك الشهري لجميع الأصول النشطة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        active_assets = conn.execute(
            "SELECT id FROM fixed_assets "
            "WHERE status='نشط' AND monthly_depreciation > 0"
        ).fetchall()
    finally:
        if own_conn:
            close_connection(conn)

    results = []
    for asset in active_assets:
        success, msg = run_depreciation(asset["id"])
        results.append((asset["id"], success, msg))
    return results


def get_depreciation_history(asset_id=None, limit=50, conn=None):
    """جلب سجل الإهلاكات"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        if asset_id:
            rows = conn.execute(
                "SELECT d.*, a.name as asset_name "
                "FROM depreciation_entries d "
                "JOIN fixed_assets a ON d.asset_id = a.id "
                "WHERE d.asset_id=? ORDER BY d.entry_date DESC",
                (asset_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT d.*, a.name as asset_name "
                "FROM depreciation_entries d "
                "JOIN fixed_assets a ON d.asset_id = a.id "
                "ORDER BY d.entry_date DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            close_connection(conn)


def get_assets_summary(conn=None):
    """ملخص الأصول الثابتة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        total_count = conn.execute(
            "SELECT COUNT(*) FROM fixed_assets"
        ).fetchone()[0]
        total_cost = conn.execute(
            "SELECT COALESCE(SUM(purchase_cost),0) FROM fixed_assets"
        ).fetchone()[0]
        total_dep = conn.execute(
            "SELECT COALESCE(SUM(accumulated_depreciation),0) FROM fixed_assets"
        ).fetchone()[0]
        total_book = conn.execute(
            "SELECT COALESCE(SUM(book_value),0) FROM fixed_assets"
        ).fetchone()[0]
        active_count = conn.execute(
            "SELECT COUNT(*) FROM fixed_assets WHERE status='نشط'"
        ).fetchone()[0]
        return {
            "total_count": total_count,
            "total_cost": total_cost,
            "total_depreciation": total_dep,
            "total_book_value": total_book,
            "active_count": active_count,
        }
    finally:
        if own_conn:
            close_connection(conn)
