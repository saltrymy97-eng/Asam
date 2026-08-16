# services/opening_balances_service.py – الأرصدة الافتتاحية (ديناميكية ومتكاملة محاسبياً)
import sqlite3
from datetime import date
from database import get_connection
from services.audit_service import log_action
from services.fifo_service import add_batch
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry

def create_opening_tables():
    """إنشاء جداول الأرصدة الافتتاحية إذا لم تكن موجودة"""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS opening_balances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL,
                account_id INTEGER NOT NULL,
                account_code TEXT NOT NULL,
                account_name TEXT,
                debit REAL DEFAULT 0.0,
                credit REAL DEFAULT 0.0,
                journal_entry_id INTEGER,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS opening_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                quantity REAL NOT NULL,
                unit_cost REAL NOT NULL,
                journal_entry_id INTEGER,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)
        conn.commit()
    finally:
        conn.close()

def get_accounts_for_opening():
    """
    جلب الحسابات المناسبة لإدخال الأرصدة الافتتاحية (أصول، خصوم، حقوق ملكية).
    يتم تجاهل حسابات الإيرادات والمصروفات لأنها تبدأ من الصفر مالياً.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        # استعلام محسن: نستخدم جدول accounts الصحيح، ونستبعد الحسابات التجميعية
        accounts = conn.execute("""
            SELECT id, code, name, account_type as type, level
            FROM accounts
            WHERE account_type IN ('Asset', 'Liability', 'Equity')
              AND level >= 2
            ORDER BY code
        """).fetchall()
        return [dict(a) for a in accounts]
    finally:
        conn.close()

def get_products_for_opening():
    """جلب المنتجات مع كمياتها الحالية (قبل الافتتاح) لإدخال الأرصدة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        products = conn.execute("""
            SELECT id, name, quantity, purchase_price
            FROM products
            ORDER BY name
        """).fetchall()
        return [dict(p) for p in products]
    finally:
        conn.close()

def _resolve_account_id(conn, account_identifier):
    """
    دالة مساعدة ذكية لتحويل أي معرف حساب إلى الـ ID الرقمي الأساسي.
    تدعم إما account_id مباشر أو كود الحساب (مثل '1100').
    """
    if not account_identifier:
        return None
    
    # إذا كان الرقم هو الـ ID المباشر (رقم صحيح)
    if isinstance(account_identifier, int):
        return account_identifier
    
    # تحويله لنص لفحصه
    account_identifier = str(account_identifier).strip()
    
    # محاولة تحويل النص إلى ID
    if account_identifier.isdigit():
        # قد يكون ID أو Code، نفضل البحث عن ID أولاً (لأنه أكثر دقة)
        row = conn.execute("SELECT id FROM accounts WHERE id = ?", (account_identifier,)).fetchone()
        if row:
            return row["id"]
        
        # إن لم يكن ID، نجرب البحث كـ Code
        row = conn.execute("SELECT id FROM accounts WHERE code = ?", (account_identifier,)).fetchone()
        if row:
            return row["id"]
    
    # إن لم يجد، يرجع None
    return None

def create_opening_balances(account_balances, inventory_items, entry_date, created_by="admin"):
    """
    إنشاء الأرصدة الافتتاحية مرة واحدة باستخدام الحسابات الوظيفية والمباشرة.
    account_balances: [{'account_id':..., 'code':..., 'debit':..., 'credit':...}, ...]
    inventory_items: [{'product_id':..., 'quantity':..., 'unit_cost':...}, ...]
    """
    create_opening_tables()
    
    # جلب الحسابات الوظيفية المطلوبة للمخزون والتسوية
    inventory_acc_id = get_functional_account("inventory")
    opening_diff_acc_id = get_functional_account("retained_earnings")

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        # فحص إذا كان هناك أرصدة سابقة
        existing = conn.execute("SELECT COUNT(*) as cnt FROM opening_balances").fetchone()
        if existing and existing["cnt"] > 0:
            return None, "الأرصدة الافتتاحية سبق تسجيلها. لا يمكن تكرار العملية."
        
        conn.execute("BEGIN")
        
        # 1. معالجة المخزون الافتتاحي
        total_inventory_cost = 0.0
        for item in inventory_items:
            qty = float(item.get('quantity', 0))
            cost = float(item.get('unit_cost', 0))
            if qty <= 0:
                continue
            
            # تحديث الكمية في products
            conn.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?",
                        (qty, item['product_id']))
            # إضافة دفعة FIFO
            add_batch(item['product_id'], qty, cost,
                     entry_date, reference="رصيد افتتاحي", conn=conn)
            total_inventory_cost += qty * cost
            
            # تخزين في opening_inventory
            conn.execute("""
                INSERT INTO opening_inventory (entry_date, product_id, quantity, unit_cost, created_by) 
                VALUES (?, ?, ?, ?, ?)
            """, (entry_date, item['product_id'], qty, cost, created_by))
        
        # 2. بناء سطور القيد
        lines = []
        total_debit = 0.0
        total_credit = 0.0
        
        for bal in account_balances:
            debit_val = round(float(bal.get('debit', 0.0)), 2)
            credit_val = round(float(bal.get('credit', 0.0)), 2)
            
            if debit_val == 0 and credit_val == 0:
                continue
            
            # استخراج معرف الحساب باستخدام الدالة المساعدة الذكية
            identifier = bal.get('account_id') or bal.get('code') or bal.get('account_code')
            acc_id = _resolve_account_id(conn, identifier)
            
            if not acc_id:
                raise Exception(f"لم يتم العثور على حساب برمز: {bal.get('code') or bal.get('account_id')}")

            lines.append({
                "account_id": acc_id,
                "debit": debit_val,
                "credit": credit_val,
                "currency_code": "YER",
                "exchange_rate": 1.0
            })
            total_debit += debit_val
            total_credit += credit_val
        
        # إضافة المخزون (مدين) إذا كان هناك منتجات
        if total_inventory_cost > 0:
            if not inventory_acc_id:
                raise Exception("حساب المخزون الوظيفي (inventory) غير معرف في شجرة الحسابات")
            
            lines.append({
                "account_id": inventory_acc_id,
                "debit": round(total_inventory_cost, 2),
                "credit": 0.0,
                "currency_code": "YER",
                "exchange_rate": 1.0
            })
            total_debit += round(total_inventory_cost, 2)
        
        # موازنة القيد: إذا كان هناك فرق، نضعه في حساب الأرباح المبقاة
        diff = round(total_debit - total_credit, 2)
        if abs(diff) > 0.01:
            if not opening_diff_acc_id:
                raise Exception("حساب الأرباح المبقاة الوظيفي (retained_earnings) غير معرف في الشجرة")

            if diff > 0:
                lines.append({
                    "account_id": opening_diff_acc_id,
                    "debit": 0.0,
                    "credit": diff,
                    "currency_code": "YER",
                    "exchange_rate": 1.0
                })
            else:
                lines.append({
                    "account_id": opening_diff_acc_id,
                    "debit": abs(diff),
                    "credit": 0.0,
                    "currency_code": "YER",
                    "exchange_rate": 1.0
                })
        
        # 3. إنشاء قيد الافتتاح
        entry_id, error = save_journal_entry(
            description=f"قيد الأرصدة الافتتاحية - {entry_date}",
            lines=lines,
            entry_date=entry_date,
            conn=conn
        )
        if error:
            raise Exception(f"فشل إنشاء القيد المحاسبي: {error}")
        
        # 4. تخزين تفاصيل الأرصدة الافتتاحية
        for bal in account_balances:
            debit_val = round(float(bal.get('debit', 0.0)), 2)
            credit_val = round(float(bal.get('credit', 0.0)), 2)
            if debit_val == 0 and credit_val == 0:
                continue
            
            # نستخدم الرمز للحفظ
            account_code = bal.get('code') or bal.get('account_code') or str(bal.get('account_id'))
            
            conn.execute("""
                INSERT INTO opening_balances (entry_date, account_id, account_code, account_name, debit, credit, journal_entry_id, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (entry_date, acc_id, account_code, bal.get('name', ''), debit_val, credit_val, entry_id, created_by))
        
        # تحديث opening_inventory برقم القيد
        conn.execute("UPDATE opening_inventory SET journal_entry_id=? WHERE entry_date=? AND journal_entry_id IS NULL",
                    (entry_id, entry_date))
        
        conn.commit()
        
        log_action(username=created_by, action="تسجيل الأرصدة الافتتاحية",
                  table_name="opening_balances", record_id=entry_id,
                  new_value=f"رقم القيد الافتتاحي: {entry_id}")
        
        return entry_id, None
    except Exception as e:
        conn.rollback()
        return None, str(e)
    finally:
        conn.close()
