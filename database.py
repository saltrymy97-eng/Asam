import sqlite3
from datetime import datetime
import hashlib

# ============================================================
#                         الاتصال بقاعدة البيانات
# ============================================================

def get_conn():
    conn = sqlite3.connect('erp.db')
    conn.row_factory = sqlite3.Row
    return conn

# ============================================================
#                         ترقية قاعدة البيانات
# ============================================================

def upgrade_database():
    """تحديث هيكل الجداول القديمة إلى الجديد (آمن للتشغيل عدة مرات)"""
    conn = get_conn()
    cursor = conn.cursor()
    
    for col in ['movement_type', 'notes']:
        try:
            cursor.execute(f"ALTER TABLE inventory_movements ADD COLUMN {col} TEXT")
        except:
            pass
    for col in ['vat_amount', 'vat_rate', 'returned_qty']:
        try:
            cursor.execute(f"ALTER TABLE sales ADD COLUMN {col} REAL DEFAULT 0")
        except:
            pass
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN vat_rate REAL DEFAULT 0.0")
    except:
        pass
    conn.commit()
    conn.close()

# ============================================================
#                         تهيئة الجداول
# ============================================================

def init_db():
    conn = get_conn()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        price REAL NOT NULL,
        stock INTEGER NOT NULL DEFAULT 0,
        vat_rate REAL DEFAULT 0.0)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS inventory_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        qty INTEGER NOT NULL,
        movement_type TEXT NOT NULL,
        date_time TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        notes TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        qty INTEGER NOT NULL,
        total REAL NOT NULL,
        vat_amount REAL DEFAULT 0,
        vat_rate REAL DEFAULT 0,
        returned_qty INTEGER DEFAULT 0,
        date_time TEXT NOT NULL DEFAULT (datetime('now','localtime')))''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        address TEXT,
        balance REAL NOT NULL DEFAULT 0.0)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS customer_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        date TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        type TEXT NOT NULL,
        amount REAL NOT NULL,
        reference_id INTEGER,
        notes TEXT)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        balance REAL NOT NULL DEFAULT 0.0)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER NOT NULL,
        date TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        total REAL NOT NULL)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS purchase_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        qty INTEGER NOT NULL,
        unit_cost REAL NOT NULL)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('asset','liability','equity','revenue','expense')),
        parent_id INTEGER)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS journal_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        description TEXT,
        reference_type TEXT,
        reference_id INTEGER)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS journal_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_id INTEGER NOT NULL,
        account_id INTEGER NOT NULL,
        debit REAL NOT NULL DEFAULT 0,
        credit REAL NOT NULL DEFAULT 0)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS vat_settings (
        id INTEGER PRIMARY KEY,
        default_rate REAL DEFAULT 0.15,
        is_enabled INTEGER DEFAULT 1)''')
    
    cursor.execute("SELECT COUNT(*) FROM vat_settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO vat_settings (id, default_rate, is_enabled) VALUES (1, 0.15, 1)")
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS fixed_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        purchase_date TEXT NOT NULL,
        purchase_cost REAL NOT NULL,
        salvage_value REAL DEFAULT 0,
        useful_life_years INTEGER NOT NULL,
        current_value REAL,
        accumulated_depreciation REAL DEFAULT 0,
        status TEXT DEFAULT 'active')''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS warehouses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        location TEXT,
        is_main INTEGER DEFAULT 0)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        position TEXT,
        department TEXT,
        hire_date TEXT,
        salary REAL DEFAULT 0,
        phone TEXT,
        email TEXT,
        status TEXT DEFAULT 'active')''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS bom (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        component_name TEXT NOT NULL,
        quantity REAL NOT NULL)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS production_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT UNIQUE,
        product_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        status TEXT DEFAULT 'planned',
        created_at TEXT DEFAULT (datetime('now','localtime')))''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL)''')
    
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)", ('admin', admin_hash, 'admin'))
    
    conn.commit()
    conn.close()
    create_default_accounts()

def create_default_accounts():
    defaults = [(1, 'الصندوق', 'asset'), (2, 'العملاء', 'asset'),
                (3, 'المخزون', 'asset'), (4, 'المبيعات', 'revenue'),
                (5, 'الموردين', 'liability'), (6, 'رأس المال', 'equity'),
                (7, 'مردودات المبيعات', 'revenue')]
    conn = get_conn()
    cursor = conn.cursor()
    for code, name, type_ in defaults:
        cursor.execute("INSERT OR IGNORE INTO accounts (id, code, name, type) VALUES (?,?,?,?)", (code, code, name, type_))
    conn.commit()
    conn.close()

# ============================================================
#                         دوال المنتجات والمخزون
# ============================================================

def add_product(name, price, stock, vat_rate=0.0):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO products (name, price, stock, vat_rate) VALUES (?,?,?,?)", (name, price, stock, vat_rate))
    conn.commit()
    record_movement(name, stock, 'in', 'مخزون أولي')
    conn.close()

def get_all_products():
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name, price, stock, vat_rate FROM products ORDER BY name")
    except:
        cursor.execute("SELECT id, name, price, stock FROM products ORDER BY name")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row, vat_rate=0.0) for row in rows]
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_product(product_id, name, price):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET name=?, price=? WHERE id=?", (name, price, product_id))
    if cursor.rowcount == 0:
        raise ValueError(f"Product {product_id} not found")
    conn.commit()
    conn.close()

def delete_product(product_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM products WHERE id=?", (product_id,))
    row = cursor.fetchone()
    if row:
        pname = row['name']
        cursor.execute("DELETE FROM inventory_movements WHERE product_name=?", (pname,))
        cursor.execute("DELETE FROM sales WHERE product_name=?", (pname,))
        cursor.execute("DELETE FROM purchase_items WHERE product_name=?", (pname,))
        cursor.execute("DELETE FROM products WHERE id=?", (product_id,))
        conn.commit()
    conn.close()

def update_stock(product_name, qty_change, movement_type, notes=""):
    conn = get_conn()
    cursor = conn.cursor()
    if movement_type == 'in':
        cursor.execute("UPDATE products SET stock = stock + ? WHERE name=?", (qty_change, product_name))
    else:
        cursor.execute("UPDATE products SET stock = stock - ? WHERE name=?", (qty_change, product_name))
    if cursor.rowcount == 0:
        raise ValueError(f"Product '{product_name}' not found")
    conn.commit()
    record_movement(product_name, qty_change, movement_type, notes)
    conn.close()

# ========== الدالة الصحيحة لتسجيل حركة المخزون ==========
def record_movement(product_name, qty, movement_type, notes=""):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO inventory_movements (product_name, qty, movement_type, notes) VALUES (?,?,?,?)",
                   (product_name, qty, movement_type, notes))
    conn.commit()
    conn.close()

def get_low_stock(threshold=5):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, stock FROM products WHERE stock <= ? ORDER BY stock", (threshold,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_sales_summary():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total_sales, COALESCE(SUM(total),0) as total_revenue FROM sales")
    row = cursor.fetchone()
    conn.close()
    return {'total_sales': row['total_sales'], 'total_revenue': row['total_revenue']}

# ============================================================
#                         دوال العملاء
# ============================================================

def add_customer(name, phone, address):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO customers (name, phone, address, balance) VALUES (?,?,?,0)", (name, phone, address))
    conn.commit()
    conn.close()

def get_all_customers():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, phone, address, balance FROM customers ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_customer_balance(customer_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM customers WHERE id=?", (customer_id,))
    row = cursor.fetchone()
    if row is None:
        raise ValueError("Customer not found")
    return row['balance']

def get_customer_statement(customer_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, date, type, amount, reference_id, notes FROM customer_transactions WHERE customer_id=? ORDER BY date DESC, id DESC", (customer_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_customer_transaction(customer_id, type_, amount, reference_id=None, notes=""):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO customer_transactions (customer_id, type, amount, reference_id, notes) VALUES (?,?,?,?,?)",
                   (customer_id, type_, amount, reference_id, notes))
    if type_ == 'sale':
        cursor.execute("UPDATE customers SET balance = balance + ? WHERE id=?", (amount, customer_id))
    elif type_ == 'payment':
        cursor.execute("UPDATE customers SET balance = balance - ? WHERE id=?", (amount, customer_id))
    else:
        raise ValueError("Invalid type")
    conn.commit()
    conn.close()

def receive_payment(customer_id, amount, notes=""):
    if amount <= 0:
        raise ValueError("Amount must be positive")
    add_customer_transaction(customer_id, 'payment', amount, None, notes)
    post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
               f"تحصيل دفعة من عميل {customer_id} - {notes}",
               'customer_payment', customer_id,
               [{'account_id': 1, 'debit': amount, 'credit': 0},
                {'account_id': 2, 'debit': 0, 'credit': amount}])

# ============================================================
#                         دوال الموردين والمشتريات
# ============================================================

def add_supplier(name, phone):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO suppliers (name, phone, balance) VALUES (?,?,0)", (name, phone))
    conn.commit()
    conn.close()

def get_all_suppliers():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, phone, balance FROM suppliers ORDER BY name")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_purchase(supplier_id, items):
    if not items:
        raise ValueError("يجب إضافة صنف واحد على الأقل")
    total = sum(item['qty'] * item['unit_cost'] for item in items)
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM suppliers WHERE id=?", (supplier_id,))
    if cursor.fetchone() is None:
        raise ValueError("Supplier not found")
    cursor.execute("INSERT INTO purchases (supplier_id, total) VALUES (?,?)", (supplier_id, total))
    purchase_id = cursor.lastrowid
    for item in items:
        pname, qty, cost = item['product_name'], item['qty'], item['unit_cost']
        cursor.execute("SELECT name FROM products WHERE name=?", (pname,))
        if cursor.fetchone() is None:
            raise ValueError(f"Product '{pname}' not found")
        cursor.execute("INSERT INTO purchase_items (purchase_id, product_name, qty, unit_cost) VALUES (?,?,?,?)",
                       (purchase_id, pname, qty, cost))
        cursor.execute("UPDATE products SET stock = stock + ? WHERE name=?", (qty, pname))
        record_movement(pname, qty, 'in', f'شراء فاتورة {purchase_id}')
    cursor.execute("UPDATE suppliers SET balance = balance + ? WHERE id=?", (total, supplier_id))
    conn.commit()
    post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
               f"فاتورة شراء رقم {purchase_id} من مورد {supplier_id}",
               'purchase', purchase_id,
               [{'account_id': 3, 'debit': total, 'credit': 0},
                {'account_id': 5, 'debit': 0, 'credit': total}])
    conn.close()
    return purchase_id

def pay_supplier(supplier_id, amount, notes=""):
    if amount <= 0:
        raise ValueError("Amount must be positive")
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, balance FROM suppliers WHERE id=?", (supplier_id,))
    row = cursor.fetchone()
    if row is None:
        raise ValueError("Supplier not found")
    if amount > row['balance']:
        raise ValueError("المبلغ أكبر من الرصيد")
    cursor.execute("UPDATE suppliers SET balance = balance - ? WHERE id=?", (amount, supplier_id))
    conn.commit()
    conn.close()
    post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
               f"دفع للمورد {supplier_id} - {notes}",
               'supplier_payment', supplier_id,
               [{'account_id': 5, 'debit': amount, 'credit': 0},
                {'account_id': 1, 'debit': 0, 'credit': amount}])

# ============================================================
#                         دوال المبيعات والمحاسبة
# ============================================================

def add_sale(product_name, qty, total, vat_amount=0, vat_rate=0):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sales (product_name, qty, total, vat_amount, vat_rate) VALUES (?,?,?,?,?)",
                   (product_name, qty, total, vat_amount, vat_rate))
    conn.commit()
    sale_id = cursor.lastrowid
    conn.close()
    return sale_id

def add_sale_with_customer(product_name, qty, total, vat_amount, vat_rate, customer_id=None):
    sale_id = add_sale(product_name, qty, total, vat_amount, vat_rate)
    update_stock(product_name, qty, 'out', f'بيع')
    if customer_id is not None:
        add_customer_transaction(customer_id, 'sale', total, sale_id, f'فاتورة بيع {product_name}')
        post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                   f"بيع آجل - فاتورة {sale_id} للعميل {customer_id}",
                   'sale', sale_id,
                   [{'account_id': 2, 'debit': total, 'credit': 0},
                    {'account_id': 4, 'debit': 0, 'credit': total}])
    else:
        post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                   f"بيع نقدي - فاتورة {sale_id}",
                   'sale', sale_id,
                   [{'account_id': 1, 'debit': total, 'credit': 0},
                    {'account_id': 4, 'debit': 0, 'credit': total}])
    return sale_id

def post_entry(date, description, ref_type, ref_id, details):
    if not details:
        raise ValueError("تفاصيل مطلوبة")
    total_debit = sum(d['debit'] for d in details)
    total_credit = sum(d['credit'] for d in details)
    if abs(total_debit - total_credit) > 0.001:
        raise ValueError("القيد غير متوازن")
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO journal_entries (date, description, reference_type, reference_id) VALUES (?,?,?,?)",
                   (date, description, ref_type, ref_id))
    entry_id = cursor.lastrowid
    for d in details:
        cursor.execute("INSERT INTO journal_details (entry_id, account_id, debit, credit) VALUES (?,?,?,?)",
                       (entry_id, d['account_id'], d['debit'], d['credit']))
    conn.commit()
    conn.close()
    return entry_id

def get_account_balance(account_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT type FROM accounts WHERE id=?", (account_id,))
    row = cursor.fetchone()
    if not row:
        return 0.0
    acc_type = row['type']
    cursor.execute("SELECT COALESCE(SUM(debit),0) as d, COALESCE(SUM(credit),0) as c FROM journal_details WHERE account_id=?",
                   (account_id,))
    sums = cursor.fetchone()
    debit, credit = sums['d'], sums['c']
    if acc_type in ('asset', 'expense'):
        return debit - credit
    else:
        return credit - debit
    conn.close()

def get_accounts_tree():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, code, name, type, parent_id FROM accounts ORDER BY code")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_journal_entries():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT je.id, je.date, je.description, je.reference_type, je.reference_id,
               jd.account_id, a.name as account_name, jd.debit, jd.credit
        FROM journal_entries je
        JOIN journal_details jd ON je.id = jd.entry_id
        JOIN accounts a ON jd.account_id = a.id
        ORDER BY je.date DESC, je.id DESC""")
    rows = cursor.fetchall()
    conn.close()
    entries = {}
    for row in rows:
        eid = row['id']
        if eid not in entries:
            entries[eid] = {
                'id': eid,
                'date': row['date'],
                'description': row['description'],
                'reference_type': row['reference_type'],
                'reference_id': row['reference_id'],
                'details': []
            }
        entries[eid]['details'].append({
            'account_id': row['account_id'],
            'account_name': row['account_name'],
            'debit': row['debit'],
            'credit': row['credit']
        })
    return list(entries.values())

# ============================================================
#                         دوال الضريبة
# ============================================================

def get_vat_settings():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT default_rate, is_enabled FROM vat_settings WHERE id=1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return {'default_rate': row['default_rate'], 'is_enabled': row['is_enabled']}
    else:
        return {'default_rate': 0.15, 'is_enabled': 1}

def update_vat_settings(rate, enabled):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE vat_settings SET default_rate=?, is_enabled=?", (rate, 1 if enabled else 0))
    conn.commit()
    conn.close()

# ============================================================
#                         دوال المرتجعات
# ============================================================

def get_all_sales_invoices():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.date_time, s.product_name, s.qty, s.total, s.returned_qty,
               c.name as customer_name
        FROM sales s
        LEFT JOIN customer_transactions ct ON s.id = ct.reference_id AND ct.type='sale'
        LEFT JOIN customers c ON ct.customer_id = c.id
        ORDER BY s.date_time DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    invoices = {}
    for row in rows:
        inv_id = row['id']
        if inv_id not in invoices:
            invoices[inv_id] = {'id': inv_id, 'date': row['date_time'], 'customer': row['customer_name'] or 'نقدي', 'items': []}
        invoices[inv_id]['items'].append({'product': row['product_name'], 'qty': row['qty'], 'returned': row['returned_qty'] or 0, 'total': row['total']})
    return list(invoices.values())

def process_return(sale_id, product_name, return_qty):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT qty, total FROM sales WHERE id=? AND product_name=?", (sale_id, product_name))
        sale = cursor.fetchone()
        if not sale:
            raise ValueError("البيع غير موجود")
        if return_qty <= 0:
            raise ValueError("كمية المرتجع يجب أن تكون أكبر من صفر")
        if return_qty > sale['qty']:
            raise ValueError("كمية المرتجع أكبر من الكمية المباعة")
        cursor.execute("UPDATE sales SET returned_qty = returned_qty + ? WHERE id=? AND product_name=?", (return_qty, sale_id, product_name))
        refund_amount = (return_qty / sale['qty']) * sale['total']
        cursor.execute("UPDATE products SET stock = stock + ? WHERE name=?", (return_qty, product_name))
        record_movement(product_name, return_qty, 'return', f'مرتجع من فاتورة {sale_id}')
        cursor.execute("SELECT ct.customer_id FROM customer_transactions ct WHERE ct.reference_id=? AND ct.type='sale' LIMIT 1", (sale_id,))
        cust_row = cursor.fetchone()
        if cust_row:
            cursor.execute("UPDATE customers SET balance = balance - ? WHERE id=?", (refund_amount, cust_row['customer_id']))
            cursor.execute("INSERT INTO customer_transactions (customer_id, type, amount, reference_id, notes) VALUES (?,?,?,?,?)",
                           (cust_row['customer_id'], 'return', refund_amount, sale_id, f'مرتجع فاتورة {sale_id}'))
            post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f"مرتجع مبيعات من فاتورة {sale_id}", 'sales_return', sale_id,
                       [{'account_id': 7, 'debit': refund_amount, 'credit': 0}, {'account_id': 2, 'debit': 0, 'credit': refund_amount}])
        else:
            post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f"مرتجع مبيعات نقدي من فاتورة {sale_id}", 'sales_return', sale_id,
                       [{'account_id': 7, 'debit': refund_amount, 'credit': 0}, {'account_id': 1, 'debit': 0, 'credit': refund_amount}])
        conn.commit()
        return refund_amount
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# ============================================================
#                         دوال التقارير المتقدمة
# ============================================================

def advanced_report():
    import streamlit as st
    import pandas as pd
    import plotly.express as px
    conn = get_conn()
    sales_df = pd.read_sql("SELECT date_time, total FROM sales", conn)
    conn.close()
    if not sales_df.empty:
        sales_df['date'] = pd.to_datetime(sales_df['date_time']).dt.date
        daily = sales_df.groupby('date')['total'].sum().reset_index()
        fig = px.line(daily, x='date', y='total', title='المبيعات اليومية', markers=True, color_discrete_sequence=['#6a0dad'])
        fig.update_layout(plot_bgcolor='white', title_font_color='#1a1a2e')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد بيانات مبيعات")
