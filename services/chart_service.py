# services/chart_service.py – منطق شجرة الحسابات (مع دعم النوع الوظيفي)
import sqlite3
from database import get_connection
from services.audit_service import log_action

# الأنواع الوظيفية المتاحة
FUNCTIONAL_TYPES = {
    "cash": "صندوق النقدية",
    "bank": "حساب بنكي",
    "customers": "العملاء (ذمم مدينة)",
    "suppliers": "الموردين (ذمم دائنة)",
    "inventory": "المخزون",
    "sales_revenue": "إيرادات المبيعات",
    "cogs": "تكلفة البضاعة المباعة",
    "vat_payable": "ضريبة القيمة المضافة المستحقة",
    "vat_receivable": "ضريبة القيمة المضافة المدخلة",
    "expense": "مصروف",
    "fixed_asset": "أصل ثابت",
    "depreciation": "مجمع الإهلاك",
    "equity": "حقوق ملكية",
    "salary": "رواتب",
    "retained_earnings": "أرباح محتجزة",
}

def create_accounts_table():
    """إنشاء جدول الحسابات إذا لم يكن موجوداً"""
    conn = get_connection()
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
    conn.close()

def add_account(code, name, parent_id=None, account_type=None, functional_type=None):
    """إضافة حساب جديد مع حماية العملية ودعم النوع الوظيفي"""
    level = 1
    if parent_id:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        parent = conn.execute("SELECT level FROM accounts WHERE id=?", (parent_id,)).fetchone()
        if parent:
            level = parent["level"] + 1
        conn.close()
    
    is_debit = "credit" if code.startswith(("2", "3", "4")) else "debit"
    
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO accounts (code, name, parent_id, level, is_debit, account_type, functional_type) VALUES (?,?,?,?,?,?,?)",
            (code, name, parent_id, level, is_debit, account_type, functional_type)
        )
        conn.commit()

        # تسجيل العملية في سجل التدقيق
        log_action(
            username="admin",
            action="إضافة حساب",
            table_name="accounts",
            new_value=f"الكود: {code}, الاسم: {name}, المستوى: {level}, التصنيف: {account_type or 'غير محدد'}, النوع الوظيفي: {functional_type or 'غير محدد'}"
        )

        return True, None
    except sqlite3.IntegrityError:
        conn.rollback()
        return False, "الكود موجود مسبقاً"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_accounts_tree():
    """جلب جميع الحسابات مرتبة مع التصنيف والنوع الوظيفي"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    accounts = conn.execute("SELECT id, code, name, parent_id, level, is_debit, account_type, functional_type FROM accounts ORDER BY code").fetchall()
    conn.close()
    return accounts

def build_tree(accounts, parent_id=None, indent=0):
    """بناء شجرة حسابات هرمية"""
    tree = []
    for acc in accounts:
        if acc["parent_id"] == parent_id:
            acc_dict = dict(acc)
            acc_dict["indent"] = indent
            tree.append(acc_dict)
            tree.extend(build_tree(accounts, acc["id"], indent + 1))
    return tree

def get_account_options():
    """جلب خيارات الحسابات للقائمة المنسدلة"""
    accounts = get_accounts_tree()
    options = {"لا شيء (حساب رئيسي)": None}
    for acc in accounts:
        prefix = " " * (acc["level"] - 1) if acc["level"] else ""
        options[f"{prefix}{acc['code']} - {acc['name']}"] = acc["id"]
    return options

def get_functional_account(functional_type):
    """
    البحث عن حساب حسب نوعه الوظيفي.
    ترجع كود الحساب (code) إذا وجد، أو ترسل خطأ إذا لم يوجد.
    
    Parameters:
    - functional_type: مثل 'cash', 'sales_revenue', 'customers', إلخ.
    
    Returns:
    - كود الحساب (نص).
    
    Raises:
    - ValueError إذا لم يتم العثور على حساب بهذا النوع الوظيفي.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT code, name FROM accounts WHERE functional_type = ? AND is_active = 1 LIMIT 1",
        (functional_type,)
    ).fetchone()
    conn.close()
    
    if row:
        return row["code"]
    else:
        type_name = FUNCTIONAL_TYPES.get(functional_type, functional_type)
        raise ValueError(f"لم يتم العثور على حساب بالنوع الوظيفي '{type_name}'. يرجى إضافة حساب بهذا النوع في شجرة الحسابات.")
