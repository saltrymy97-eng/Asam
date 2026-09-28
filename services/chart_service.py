# services/chart_service.py – منطق شجرة الحسابات (v2.0)
# ✅ Connection Registry — لا يُغلق الاتصال
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
    "inventory_gain": "(inventory_gain) عجز/خسائر المخزون",
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
                FOREIGN KEY (parent_id) REFERENCES accounts(id) ON DELETE SET NULL
            )
        """)
        conn.commit()
    finally:
        close_connection(conn)


def add_account(code, name, parent_id=None, account_type=None,
                functional_type=None, conn=None):
    """إضافة حساب جديد."""
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

        c.execute(
            "INSERT INTO accounts "
            "(code, name, parent_id, level, is_debit, account_type, functional_type) "
            "VALUES (?,?,?,?,?,?,?)",
            (code, name, parent_id, level, is_debit, account_type, functional_type)
        )

        if owns:
            c.execute("COMMIT")

        log_action(username="admin", action="إضافة حساب", table_name="accounts",
                   new_value=f"الكود: {code}, الاسم: {name}, المستوى: {level}, "
                             f"التصنيف: {account_type or 'غير محدد'}, "
                             f"النوع الوظيفي: {functional_type or 'غير محدد'}")
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


def get_accounts_tree(conn=None):
    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row
        accounts = c.execute("""
            SELECT id, code, name, parent_id, level, is_debit, is_active,
                   account_type, functional_type
            FROM accounts
            ORDER BY LENGTH(code), code
        """).fetchall()
        return accounts
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


def get_account_options(conn=None):
    accounts = get_accounts_tree(conn=conn)
    options = {"لا شيء (حساب رئيسي)": None}
    for acc in accounts:
        prefix = " " * (acc["level"] - 1) if acc["level"] else ""
        options[f"{prefix}{acc['code']} - {acc['name']}"] = acc["id"]
    return options


def get_functional_account(functional_type, conn=None):
    """
    إرجاع كود الحساب حسب النوع الوظيفي.
    ✅ لا يُغلق الاتصال المُمرَّر أو المشترك.
    """
    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row
        row = c.execute(
            "SELECT code, name FROM accounts "
            "WHERE functional_type = ? AND is_active = 1 LIMIT 1",
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


def delete_account(account_id, conn=None):
    c, owns = _resolve_conn(conn)
    try:
        try:
            used = c.execute(
                "SELECT COUNT(*) FROM journal_lines WHERE account_id = ?",
                (account_id,)
            ).fetchone()[0]
        except sqlite3.OperationalError:
            used = 0

        if used > 0:
            return False, "لا يمكن حذف هذا الحساب لأنه مستخدم في قيود محاسبية."

        if owns:
            c.execute("BEGIN IMMEDIATE")
        c.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        if owns:
            c.execute("COMMIT")

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
