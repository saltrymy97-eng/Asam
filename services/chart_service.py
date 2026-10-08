# services/chart_service.py – منطق شجرة الحسابات (v3.1)
# ✅ Connection Registry — لا يُغلق الاتصال
# ✅ v2.1: تسجيل كامل (username + record_id + dict) + تسجيل الحذف
# ✅ v3.0: دعم is_system (الحسابات النظامية) + حماية
# ✅ v3.1: إصلاح — get_accounts_tree تُعيد dict بدل sqlite3.Row (لدعم .get())
import sqlite3
from database import get_connection, close_connection
from services.audit_service import log_action

# خيارات الأنواع الوظيفية
FUNCTIONAL_TYPES = {
    "None": "بدون (حساب عادي/فرعي)",
    "cash": "(cash) النقدية/الصندوق",
    "bank": "(bank) البنك",
    "inventory": "(inventory) المخزون",
    "accounts_receivable": "(accounts_receivable) العملاء/مدينون",
    "accounts_payable": "(accounts_payable) الموردون/دائنون",
    "sales_revenue": "(sales_revenue) إيرادات المبيعات",
    "cogs": "(cogs) تكلفة البضاعة المباعة",
    "sales_tax": "(sales_tax) ضريبة المبيعات/مخرجات",
    "purchase_tax": "(purchase_tax) ضريبة المشتريات/مدخلات",
    "operating_expense": "(operating_expense) المصروفات العامة",
    "capital": "(capital) رأس المال",
    "retained_earnings": "(retained_earnings) الأرباح المبقاة",
    "depreciation_expense": "(depreciation_expense) مصروف الإهلاك",
    "accumulated_depreciation": "(accumulated_depreciation) مجمع الإهلاك",
    "salaries_expense": "(salaries_expense) مصروف الرواتب",
    "accrued_expenses": "(accrued_expenses) المصروفات المستحقة",
    "inventory_gain": "(inventory_gain) أرباح/زيادة المخزون",
    "inventory_loss": "(inventory_loss) خسائر/نقص الجرد",
    "exchange_difference": "(exchange_difference) فروق أسعار الصرف",
}


def _resolve_conn(conn):
    """يرجع (conn, owns)"""
    if conn is None:
        return get_connection(), True
    return conn, False


def create_accounts_table():
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                parent_id INTEGER,
                level INTEGER DEFAULT 1,
                is_debit TEXT DEFAULT 'debit',
                is_active INTEGER CHECK(is_active IN (0,1)) DEFAULT 1,
                account_type TEXT CHECK(account_type IN ('Asset','Liability','Equity','Revenue','Expense')),
                functional_type TEXT,
                is_system INTEGER DEFAULT 0 CHECK(is_system IN (0,1)),
                FOREIGN KEY (parent_id) REFERENCES accounts(id) ON DELETE SET NULL
            )
        """)
        conn.commit()
    finally:
        close_connection(conn)


def add_account(code, name, parent_id=None, account_type=None,
                functional_type=None, conn=None, created_by="admin"):
    """
    إضافة حساب جديد.
    ✅ v2.1: يسجّل مَن أضاف (created_by) + رقم الحساب (record_id)
    """
    c, owns = _resolve_conn(conn)
    try:
        level = 1
        if parent_id:
            c.row_factory = sqlite3.Row
            parent = c.execute(
                "SELECT level FROM accounts WHERE id=?", (parent_id,)
            ).fetchone()
            if parent:
                level = parent["level"] + 1

        is_debit = "credit" if code.startswith(("2", "3", "4")) else "debit"

        if owns:
            c.execute("BEGIN IMMEDIATE")

        cur = c.execute(
            "INSERT INTO accounts "
            "(code, name, parent_id, level, is_debit, account_type, functional_type) "
            "VALUES (?,?,?,?,?,?,?)",
            (code, name, parent_id, level, is_debit, account_type, functional_type)
        )
        new_id = cur.lastrowid

        if owns:
            c.execute("COMMIT")

        try:
            log_action(
                username=created_by,
                action="📂 إضافة حساب",
                table_name="accounts",
                record_id=new_id,
                new_value={
                    "code": code,
                    "name": name,
                    "parent_id": parent_id,
                    "level": level,
                    "account_type": account_type or "غير محدد",
                    "functional_type": functional_type or "غير محدد",
                },
            )
        except Exception as e:
            print(f"⚠️ فشل تسجيل إضافة الحساب: {e}")

        return True, None

    except sqlite3.IntegrityError:
        if owns:
            try:
                c.execute("ROLLBACK")
            except Exception:
                pass
        return False, "الكود موجود مسبقاً"
    except Exception as e:
        if owns:
            try:
                c.execute("ROLLBACK")
            except Exception:
                pass
        return False, f"خطأ غير متوقع: {e}"
    finally:
        if owns:
            close_connection(c)


# ============================================================
# ✅ v3.1: get_accounts_tree — يُعيد list of dict
# ============================================================
def get_accounts_tree(conn=None):
    """
    جلب شجرة الحسابات.
    ✅ v3.0: يُعيد عمود is_system أيضاً
    ✅ v3.1: يُعيد list of dict (بدل sqlite3.Row) — لدعم .get()
    """
    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row
        accounts = c.execute("""
            SELECT id, code, name, parent_id, level, is_debit, is_active,
                   account_type, functional_type, is_system
            FROM accounts
            ORDER BY LENGTH(code), code
        """).fetchall()
        # ✅ v3.1: تحويل إلى list of dict
        return [dict(a) for a in accounts]
    finally:
        if owns:
            close_connection(c)


def build_tree(accounts, parent_id=None, indent=0):
    tree = []
    for acc in accounts:
        if acc["parent_id"] == parent_id:
            acc_dict = dict(acc)
            acc_dict["indent"] = indent
            tree.append(acc_dict)
            tree.extend(build_tree(accounts, acc["id"], indent + 1))
    return tree


# ============================================================
# ✅ get_account_options — يستثني النظامية والفرعية
# ============================================================
def get_account_options(conn=None, include_system=False,
                        include_subsidiary=False):
    """
    جلب خيارات الحساب (للقوائم المنسدلة).
    """
    accounts = get_accounts_tree(conn=conn)
    options = {"لا شيء (حساب رئيسي)": None}
    for acc in accounts:
        # ✅ فلترة النظامية
        if not include_system and acc.get("is_system", 0):
            continue
        # ✅ فلترة الفرعية (تحتوي على نقطة في الكود)
        if not include_subsidiary and "." in acc["code"]:
            continue

        prefix = " " * (acc["level"] - 1) if acc["level"] else ""
        options[f"{prefix}{acc['code']} - {acc['name']}"] = acc["id"]
    return options


# ============================================================
# ✅ get_functional_account — يختار الأب فقط (لا الفرعي)
# ============================================================
def get_functional_account(functional_type, conn=None):
    """
    إرجاع كود الحساب حسب النوع الوظيفي.
    ✅ v3.0: يستثني الحسابات النظامية (الفرعية).
    """
    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row
        row = c.execute(
            "SELECT code, name FROM accounts "
            "WHERE functional_type = ? AND is_active = 1 "
            "AND (is_system IS NULL OR is_system = 0) "
            "LIMIT 1",
            (functional_type,)
        ).fetchone()
        if row:
            return row["code"]
        type_name = FUNCTIONAL_TYPES.get(functional_type, functional_type)
        raise ValueError(
            f"لم يتم العثور على حساب بالنوع الوظيفي '{type_name}'. "
            f"يرجى إضافة حساب بهذا النوع في شجرة الحسابات."
        )
    finally:
        if owns:
            close_connection(c)


# ============================================================
# ✅ delete_account — منع حذف النظامية
# ============================================================
def delete_account(account_id, conn=None, deleted_by="admin"):
    """
    حذف حساب.
    ✅ v2.1: يسجّل الحذف كاملاً مع old_value قبل الحذف.
    ✅ v3.0: منع حذف الحسابات النظامية.
    """
    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row
        acc_check = c.execute(
            "SELECT is_system FROM accounts WHERE id = ?",
            (account_id,)
        ).fetchone()
        if acc_check and acc_check["is_system"]:
            return False, "لا يمكن حذف حساب نظامي — يُدار تلقائياً من وحدات البنك/الصندوق."

        try:
            used = c.execute(
                "SELECT COUNT(*) FROM journal_lines WHERE account_id = ?",
                (account_id,)
            ).fetchone()[0]
        except sqlite3.OperationalError:
            used = 0

        if used > 0:
            return False, "لا يمكن حذف هذا الحساب لأنه مستخدم في قيود محاسبية."

        account = c.execute(
            "SELECT id, code, name, parent_id, level, account_type, "
            "functional_type FROM accounts WHERE id = ?",
            (account_id,)
        ).fetchone()

        if not account:
            return False, "الحساب غير موجود."

        old_data = dict(account)

        if owns:
            c.execute("BEGIN IMMEDIATE")
        c.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        if owns:
            c.execute("COMMIT")

        try:
            log_action(
                username=deleted_by,
                action="🗑️ حذف حساب",
                table_name="accounts",
                record_id=account_id,
                old_value=old_data,
                new_value=f"تم حذف الحساب: {old_data.get('code')} - {old_data.get('name')}",
            )
        except Exception as e:
            print(f"⚠️ فشل تسجيل حذف الحساب: {e}")

        return True, "تم حذف الحساب بنجاح."

    except Exception as e:
        if owns:
            try:
                c.execute("ROLLBACK")
            except Exception:
                pass
        return False, str(e)
    finally:
        if owns:
            close_connection(c)


# إنشاء الجدول تلقائياً عند الاستيراد
create_accounts_table()
