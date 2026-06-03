# services/opening_balances_service.py – الأرصدة الافتتاحية (متكاملة محاسبياً)
import sqlite3
from datetime import date
from database import get_connection
from services.audit_service import log_action
from services.fifo_service import add_batch
from services.accounting_service import save_journal_entry

def create_opening_tables():
    """إنشاء جداول الأرصدة الافتتاحية إذا لم تكن موجودة"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS opening_balances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL,
            account_code TEXT NOT NULL,
            account_name TEXT,
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0,
            journal_entry_id INTEGER,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    conn.close()

def get_accounts_for_opening():
    """جلب جميع الحسابات (ما عدا الفرعية جداً) لإدخال الأرصدة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    accounts = conn.execute("""
        SELECT code, name, level, is_debit
        FROM accounts
        WHERE level <= 3
        ORDER BY code
    """).fetchall()
    conn.close()
    return [dict(a) for a in accounts]

def get_products_for_opening():
    """جلب المنتجات مع كمياتها الحالية (قبل الافتتاح) لإدخال الأرصدة"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    products = conn.execute("""
        SELECT id, name, quantity, purchase_price
        FROM products
        ORDER BY name
    """).fetchall()
    conn.close()
    return [dict(p) for p in products]

def create_opening_balances(account_balances, inventory_items, entry_date, created_by="admin"):
    """
    إنشاء الأرصدة الافتتاحية مرة واحدة.
    account_balances: [{'code':..., 'debit':..., 'credit':...}, ...]
    inventory_items: [{'product_id':..., 'quantity':..., 'unit_cost':...}, ...]
    """
    create_opening_tables()
    
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
            if item['quantity'] <= 0:
                continue
            # تحديث الكمية في products
            conn.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?",
                        (item['quantity'], item['product_id']))
            # إضافة دفعة FIFO
            add_batch(item['product_id'], item['quantity'], item['unit_cost'],
                     entry_date, reference="رصيد افتتاحي", conn=conn)
            total_inventory_cost += item['quantity'] * item['unit_cost']
            
            # تخزين في opening_inventory
            conn.execute("INSERT INTO opening_inventory (entry_date, product_id, quantity, unit_cost, created_by) VALUES (?,?,?,?,?)",
                        (entry_date, item['product_id'], item['quantity'], item['unit_cost'], created_by))
        
        # 2. بناء سطور القيد
        lines = []
        total_debit = 0.0
        total_credit = 0.0
        
        for bal in account_balances:
            if bal['debit'] == 0 and bal['credit'] == 0:
                continue
            lines.append({
                "account": bal['code'],
                "debit": bal['debit'],
                "credit": bal['credit']
            })
            total_debit += bal['debit']
            total_credit += bal['credit']
        
        # إضافة المخزون (مدين) إذا كان هناك منتجات
        if total_inventory_cost > 0:
            lines.append({
                "account": "المخزون",
                "debit": total_inventory_cost,
                "credit": 0
            })
            total_debit += total_inventory_cost
        
        # موازنة القيد: إذا كان هناك فرق، نضعه في حساب "فروق الأرصدة الافتتاحية"
        diff = total_debit - total_credit
        if abs(diff) > 0.01:
            if diff > 0:
                lines.append({
                    "account": "فروق الأرصدة الافتتاحية",
                    "debit": 0,
                    "credit": diff
                })
            else:
                lines.append({
                    "account": "فروق الأرصدة الافتتاحية",
                    "debit": -diff,
                    "credit": 0
                })
        
        # 3. إنشاء قيد الافتتاح
        entry_id, error = save_journal_entry(
            description=f"قيد الأرصدة الافتتاحية - {entry_date}",
            lines=lines,
            entry_date=entry_date,
            conn=conn
        )
        if error:
            raise Exception(f"فشل القيد المحاسبي: {error}")
        
        # 4. تخزين تفاصيل الأرصدة الافتتاحية
        for bal in account_balances:
            if bal['debit'] == 0 and bal['credit'] == 0:
                continue
            conn.execute("""
                INSERT INTO opening_balances (entry_date, account_code, account_name, debit, credit, journal_entry_id, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (entry_date, bal['code'], bal.get('name', ''), bal['debit'], bal['credit'], entry_id, created_by))
        
        # تحديث opening_inventory برقم القيد
        conn.execute("UPDATE opening_inventory SET journal_entry_id=? WHERE entry_date=? AND journal_entry_id IS NULL",
                    (entry_id, entry_date))
        
        conn.commit()
        
        log_action(username=created_by, action="تسجيل الأرصدة الافتتاحية",
                  table_name="opening_balances", record_id=entry_id,
                  new_value=f"القيد: {entry_id}")
        
        return entry_id, None
    except Exception as e:
        conn.rollback()
        return None, str(e)
    finally:
        conn.close()
