# services/chart_service.py – منطق شجرة الحسابات (مع إدارة العمليات)
import sqlite3
from database import get_connection

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
            FOREIGN KEY (parent_id) REFERENCES accounts(id)
        )
    """)
    conn.commit()
    conn.close()

def add_account(code, name, parent_id=None):
    """إضافة حساب جديد مع حماية العملية"""
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
            "INSERT INTO accounts (code, name, parent_id, level, is_debit) VALUES (?,?,?,?,?)",
            (code, name, parent_id, level, is_debit)
        )
        conn.commit()
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
    """جلب جميع الحسابات مرتبة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    accounts = conn.execute("SELECT * FROM accounts ORDER BY code").fetchall()
    conn.close()
    return accounts

def build_tree(accounts, parent_id=None, indent=0):
    """بناء شجرة حسابات هرمية"""
    tree = []
    for acc in accounts:
        if acc["parent_id"] == parent_id:
            tree.append(dict(acc, indent=indent))
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
