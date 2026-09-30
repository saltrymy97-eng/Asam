# services/assets_service.py – منطق الأصول الثابتة والإهلاكات (v2.1)
# ✅ Registry + conn=None + شراء من صندوق/بنك مع فحص الرصيد
# ✅ v2.1: نسبة الإهلاك قابلة للتحكم + إصلاح الإهلاك الزائد + منع التكرار
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
        # ✅ ترقية الجداول القديمة (آمنة)
        _safe_add_column(conn, "fixed_assets", "annual_depreciation_rate", "REAL DEFAULT 0")
        _safe_add_column(conn, "fixed_assets", "manual_monthly_depreciation", "REAL DEFAULT 0")
        _safe_add_column(conn, "fixed_assets", "last_depreciation_date", "TEXT")

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


def _safe_add_column(conn, table, column, definition):
    """إضافة عمود بأمان إذا لم يكن موجوداً (SQLite)"""
    try:
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    except Exception as e:
        print(f"⚠️ تعذر إضافة العمود {column} إلى {table}: {e}")


def _compute_monthly_depreciation(purchase_cost, salvage_value,
                                  useful_life_years,
                                  annual_rate=0.0,
                                  manual_monthly=0.0):
    """
    حساب الإهلاك الشهري حسب الأولوية:
    1) قيمة شهرية يدوية  ← الأعلى أولوية
    2) نسبة سنوية %
    3) العمر الإنتاجي (الطريقة التقليدية)
    """
    purchase_cost = float(purchase_cost or 0)
    salvage_value = float(salvage_value or 0)
    annual_rate = float(annual_rate or 0)
    manual_monthly = float(manual_monthly or 0)

    depreciable = purchase_cost - salvage_value
    if depreciable <= 0:
        return 0.0, "القيمة القابلة للإهلاك صفر أو سالبة"

    if manual_monthly > 0:
        if manual_monthly > depreciable:
            return 0.0, "الإهلاك الشهري اليدوي يتجاوز القيمة القابلة للإهلاك"
        return round(manual_monthly, 2), None

    if annual_rate > 0:
        if annual_rate > 100:
            return 0.0, "النسبة السنوية يجب أن تكون ≤ 100%"
        monthly = (depreciable * (annual_rate / 100.0)) / 12.0
        return round(monthly, 2), None

    total_months = max(1, int(useful_life_years or 5) * 12)
    return round(depreciable / total_months, 2), None


def add_asset(name, category, purchase_date, purchase_cost,
              salvage_value=0, useful_life_years=5, method="قسط ثابت",
              notes="", payment_account_code=None, payment_method="cash",
              created_by="admin", conn=None,
              annual_depreciation_rate=0.0,
              manual_monthly_depreciation=0.0):
    """إضافة أصل ثابت جديد (نسبة الإهلاك قابلة للتحكم)"""
    create_assets_tables(conn=conn)

    purchase_cost = float(purchase_cost)
    salvage_value = float(salvage_value or 0)

    if purchase_cost <= 0:
        return None, "تكلفة الشراء يجب أن تكون أكبر من صفر"
    if salvage_value < 0:
        return None, "القيمة التخريدية لا يمكن أن تكون سالبة"
    if salvage_value >= purchase_cost:
        return None, "القيمة التخريدية يجب أن تكون أقل من تكلفة الشراء"

    monthly_dep, dep_error = _compute_monthly_depreciation(
        purchase_cost=purchase_cost,
        salvage_value=salvage_value,
        useful_life_years=useful_life_years,
        annual_rate=annual_depreciation_rate,
        manual_monthly=manual_monthly_depreciation,
    )
    if dep_error:
        return None, dep_error
    if monthly_dep <= 0:
        return None, "الإهلاك الشهري المحسوب صفر"

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

        cur = conn.execute(
            """INSERT INTO fixed_assets 
               (name, category, purchase_date, purchase_cost, salvage_value,
                useful_life_years, depreciation_method, monthly_depreciation,
                book_value, notes, annual_depreciation_rate,
                manual_monthly_depreciation)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, category, purchase_date, purchase_cost, salvage_value,
             useful_life_years, method, monthly_dep, purchase_cost, notes,
             float(annual_depreciation_rate or 0),
             float(manual_monthly_depreciation or 0))
        )
        asset_id = cur.lastrowid

        if payment_account_code and payment_method in ('cash', 'bank'):
            acc_fixed_assets = get_functional_account("fixed_assets") \
                or get_functional_account("Asset") or "1401"

            lines = [
                {"account": acc_fixed_assets, "debit": purchase_cost,
                 "credit": 0, "currency_code": "YER", "exchange_rate": 1.0},
                {"account": payment_account_code, "debit": 0,
                 "credit": purchase_cost, "currency_code": "YER",
                 "exchange_rate": 1.0},
            ]

            entry_id, entry_error = save_journal_entry(
                description=f"شراء أصل ثابت: {name}",
                lines=lines,
                entry_date=purchase_date,
                conn=conn,
            )
            if entry_error:
                raise Exception(f"فشل إنشاء قيد الشراء: {entry_error}")

            if payment_method == 'cash':
                try:
                    from services.cash_service import add_cash_transaction
                    acc_row = conn.execute(
                        "SELECT id FROM cash_accounts WHERE account_code=? "
                        "AND is_active=1 LIMIT 1",
                        (payment_account_code,)
                    ).fetchone()
                    if acc_row:
                        add_cash_transaction(
                            acc_row['id'], purchase_date,
                            f"شراء أصل: {name}", 'withdrawal', purchase_cost,
                            reference=f"asset#{asset_id}",
                            create_journal=False, conn=conn,
                            skip_balance_check=True,
                        )
                except Exception as e:
                    print(f"⚠️ فشل تسجيل حركة الصندوق: {e}")
            elif payment_method == 'bank':
                try:
                    from services.bank_service import add_bank_transaction
                    acc_row = conn.execute(
                        "SELECT id FROM bank_accounts WHERE account_code=? "
                        "AND is_active=1 LIMIT 1",
                        (payment_account_code,)
                    ).fetchone()
                    if acc_row:
                        add_bank_transaction(
                            acc_row['id'], purchase_date,
                            f"شراء أصل: {name}", 'withdrawal', purchase_cost,
                            reference=f"asset#{asset_id}", conn=conn,
                            skip_balance_check=True,
                        )
                except Exception as e:
                    print(f"⚠️ فشل تسجيل حركة البنك: {e}")

        if own_conn:
            conn.commit()

        log_action(
            username=created_by, action="إضافة أصل ثابت",
            table_name="fixed_assets", record_id=asset_id,
            new_value=f"{name}, التكلفة: {purchase_cost:,.2f}, "
                      f"الإهلاك الشهري: {monthly_dep:,.2f}"
        )
        return asset_id, None

    except Exception as e:
        if own_conn:
            try: conn.rollback()
            except Exception: pass
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


def update_asset_depreciation(asset_id, annual_depreciation_rate=None,
                              manual_monthly_depreciation=None,
                              useful_life_years=None,
                              updated_by="admin", conn=None):
    """تحديث طريقة/نسبة إهلاك أصل موجود"""
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
            if own_conn: conn.rollback()
            return False, "الأصل غير موجود"

        asset = dict(asset)

        new_rate = (float(annual_depreciation_rate)
                    if annual_depreciation_rate is not None
                    else float(asset.get("annual_depreciation_rate") or 0))
        new_manual = (float(manual_monthly_depreciation)
                      if manual_monthly_depreciation is not None
                      else float(asset.get("manual_monthly_depreciation") or 0))
        new_life = (int(useful_life_years)
                    if useful_life_years is not None
                    else int(asset.get("useful_life_years") or 5))

        monthly_dep, dep_error = _compute_monthly_depreciation(
            purchase_cost=asset["purchase_cost"],
            salvage_value=asset["salvage_value"],
            useful_life_years=new_life,
            annual_rate=new_rate,
            manual_monthly=new_manual,
        )
        if dep_error:
            if own_conn: conn.rollback()
            return False, dep_error

        conn.execute(
            """UPDATE fixed_assets 
               SET annual_depreciation_rate=?,
                   manual_monthly_depreciation=?,
                   useful_life_years=?,
                   monthly_depreciation=?
               WHERE id=?""",
            (new_rate, new_manual, new_life, monthly_dep, asset_id)
        )

        if own_conn:
            conn.commit()

        log_action(
            username=updated_by, action="تعديل نسبة إهلاك",
            table_name="fixed_assets", record_id=asset_id,
            old_value=f"rate={asset.get('annual_depreciation_rate')}, "
                      f"manual={asset.get('manual_monthly_depreciation')}, "
                      f"life={asset.get('useful_life_years')}",
            new_value=f"rate={new_rate}, manual={new_manual}, "
                      f"life={new_life}, monthly={monthly_dep}"
        )
        return True, f"تم تحديث الإهلاك الشهري إلى {monthly_dep:,.2f}"

    except Exception as e:
        if own_conn:
            try: conn.rollback()
            except Exception: pass
        return False, f"فشل التحديث: {e}"
    finally:
        if own_conn:
            close_connection(conn)


def run_depreciation(asset_id, entry_date=None, notes="",
                     created_by="admin", conn=None, force=False):
    """تشغيل إهلاك شهري لأصل محدد (مع حماية من الإهلاك الزائد والتكرار)"""
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
            if own_conn: conn.rollback()
            return False, "الأصل غير موجود"
        if asset["status"] != "نشط":
            if own_conn: conn.rollback()
            return False, "الأصل غير نشط"

        monthly_dep = float(asset["monthly_depreciation"] or 0)
        if monthly_dep <= 0:
            if own_conn: conn.rollback()
            return False, "قيمة الإهلاك صفر"

        if not force:
            existing = conn.execute(
                """SELECT id FROM depreciation_entries 
                   WHERE asset_id=? 
                     AND substr(entry_date,1,7) = substr(?,1,7)
                   LIMIT 1""",
                (asset_id, entry_date)
            ).fetchone()
            if existing:
                if own_conn: conn.rollback()
                return False, ("تم إهلاك هذا الأصل مسبقاً في نفس الشهر. "
                               "استخدم force=True للتجاوز.")

        purchase_cost = float(asset["purchase_cost"] or 0)
        salvage = float(asset["salvage_value"] or 0)
        accumulated = float(asset["accumulated_depreciation"] or 0)
        remaining = round(purchase_cost - salvage - accumulated, 2)

        if remaining <= 0:
            conn.execute(
                "UPDATE fixed_assets SET status='مستنفذ', book_value=? "
                "WHERE id=?",
                (round(purchase_cost - accumulated, 2), asset_id)
            )
            if own_conn: conn.commit()
            return False, "الأصل مستنفذ بالكامل (وصل للقيمة التخريدية)"

        actual_dep = round(min(monthly_dep, remaining), 2)

        count = conn.execute(
            "SELECT COUNT(*) FROM depreciation_entries WHERE asset_id=?",
            (asset_id,)
        ).fetchone()[0] + 1

        desc = f"إهلاك {asset['name']} - الشهر {count} - {entry_date}"

        acc_dep_exp = get_functional_account("depreciation_expense")
        acc_accum_dep = get_functional_account("accumulated_depreciation")
        if not acc_dep_exp or not acc_accum_dep:
            raise Exception("حسابات الإهلاك الوظيفية غير معرفة")

        lines = [
            {"account": acc_dep_exp, "debit": actual_dep, "credit": 0,
             "currency_code": "YER", "exchange_rate": 1.0},
            {"account": acc_accum_dep, "debit": 0, "credit": actual_dep,
             "currency_code": "YER", "exchange_rate": 1.0},
        ]

        entry_id, entry_error = save_journal_entry(
            description=desc, lines=lines, entry_date=entry_date, conn=conn,
        )
        if entry_error:
            raise Exception(f"فشل إنشاء قيد الإهلاك: {entry_error}")

        new_accumulated = round(accumulated + actual_dep, 2)
        new_book_value = round(purchase_cost - new_accumulated, 2)
        new_status = "نشط" if new_book_value > salvage else "مستنفذ"

        conn.execute(
            """UPDATE fixed_assets 
               SET accumulated_depreciation=?, book_value=?, status=?,
                   last_depreciation_date=?
               WHERE id=?""",
            (new_accumulated, new_book_value, new_status,
             entry_date, asset_id)
        )

        conn.execute(
            "INSERT INTO depreciation_entries "
            "(asset_id, entry_date, amount, journal_entry_id, notes) "
            "VALUES (?, ?, ?, ?, ?)",
            (asset_id, entry_date, actual_dep, entry_id, notes)
        )

        if own_conn:
            conn.commit()

        log_action(
            username=created_by, action="إصدار إهلاك",
            table_name="depreciation_entries", record_id=entry_id,
            new_value=f"الأصل: {asset['name']}, القيمة: {actual_dep:,.2f}"
        )

        suffix = ""
        if actual_dep < monthly_dep:
            suffix = f" ⚠️ (إهلاك أخير - المتبقي كان {remaining:,.2f})"
        return True, (f"تم تسجيل إهلاك {actual_dep:.2f} "
                      f"للأصل {asset['name']} (شهر {count}){suffix}")

    except Exception as e:
        if own_conn:
            try: conn.rollback()
            except Exception: pass
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
