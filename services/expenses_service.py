# services/expenses_service.py – منطق المصروفات (محاسبة متكاملة + حسابات وظيفية)
import sqlite3
from datetime import date
from database import get_connection
from services.audit_service import log_action
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry

def create_expenses_table():
    """إنشاء جدول المصروفات إذا لم يكن موجوداً"""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                account_code TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                party_type TEXT,
                party_id INTEGER,
                invoice_ref TEXT,
                notes TEXT,
                journal_entry_id INTEGER,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()

def get_expense_categories():
    """جلب فئات المصروفات الشائعة"""
    return [
        "إيجار",
        "كهرباء",
        "مياه",
        "إنترنت",
        "رواتب",
        "صيانة",
        "نقل",
        "قرطاسية",
        "دعاية وإعلان",
        "أخرى"
    ]

def add_expense(date_val, category, amount, account_code, payment_method,
                party_type=None, party_id=None, invoice_ref=None, notes=None,
                created_by="admin"):
    """
    تسجيل مصروف مع إنشاء قيد محاسبي متزن
    """
    create_expenses_table()

    # ✅ التحقق من المبلغ
    if amount <= 0:
        return None, "المبلغ يجب أن يكون أكبر من الصفر"

    conn = get_connection()
    try:
        conn.execute("BEGIN")

        # 1. إدراج المصروف في قاعدة البيانات
        cur = conn.execute("""
            INSERT INTO expenses (date, category, amount, account_code, payment_method,
                                  party_type, party_id, invoice_ref, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (date_val, category, amount, account_code, payment_method,
              party_type, party_id, invoice_ref, notes, created_by))
        expense_id = cur.lastrowid

        # 2. الحسابات الوظيفية (تم تعديلها لتطابق شجرتك)
        # ✅ استخدام operating_expense بدلاً من expense
        expense_account = get_functional_account("operating_expense")
        
        # ✅ استخدام accounts_payable بدلاً من suppliers
        if payment_method == 'credit' and party_type == 'supplier' and party_id:
            credit_account = get_functional_account("accounts_payable")
        else:
            # إذا كان الدفع نقداً، نستخدم الكود المرسل (صندوق/بنك)
            credit_account = account_code

        if not expense_account:
            return None, "لم يتم العثور على حساب المصروفات الوظيفي (operating_expense)"

        # 3. بناء سطور القيد المحاسبي
        lines = [
            {
                "account": expense_account,  # تم التعديل هنا
                "debit": float(amount),
                "credit": 0.0,
                "currency_code": "YER",
                "exchange_rate": 1.0
            },
            {
                "account": credit_account,
                "debit": 0.0,
                "credit": float(amount),
                "currency_code": "YER",
                "exchange_rate": 1.0
            }
        ]

        # 4. إنشاء القيد
        entry_id, error = save_journal_entry(
            description=f"مصروف {category} - {date_val}",
            lines=lines,
            entry_date=date_val,
            conn=conn
        )
        if error:
            raise Exception(f"فشل إنشاء القيد المحاسبي: {error}")

        # 5. تحديث سجل المصروف برقم القيد
        conn.execute("UPDATE expenses SET journal_entry_id=? WHERE id=?", (entry_id, expense_id))

        conn.commit()

        log_action(username=created_by, action="تسجيل مصروف",
                   table_name="expenses", record_id=expense_id,
                   new_value=f"{category}: {amount:,.2f}")

        return expense_id, None
    except Exception as e:
        conn.rollback()
        return None, str(e)
    finally:
        conn.close()

def get_expenses(limit=50):
    """جلب سجل المصروفات"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        expenses = conn.execute("""
            SELECT e.*, j.id as journal_id
            FROM expenses e
            LEFT JOIN journal_entries j ON e.journal_entry_id = j.id
            ORDER BY e.id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(e) for e in expenses]
    finally:
        conn.close()

def delete_expense(expense_id):
    """حذف مصروف (مع حذف القيد المرتبط به)"""
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        
        # جلب رقم القيد المرتبط
        row = conn.execute("SELECT journal_entry_id FROM expenses WHERE id=?", (expense_id,)).fetchone()
        entry_id = row[0] if row else None
        
        # حذف القيد إذا كان موجوداً
        if entry_id:
            conn.execute("DELETE FROM journal_lines WHERE entry_id=?", (entry_id,))
            conn.execute("DELETE FROM journal_entries WHERE id=?", (entry_id,))
        
        # حذف المصروف
        conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
        
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()
