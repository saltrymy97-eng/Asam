import sqlite3
from datetime import datetime, date
import streamlit as st
import pandas as pd
import plotly.express as px

# ============================================================
#                         قاعدة البيانات
# ============================================================

def get_conn():
    conn = sqlite3.connect('erp.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    try:
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
            notes TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            balance REAL NOT NULL DEFAULT 0.0)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER NOT NULL,
            date TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            total REAL NOT NULL,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS purchase_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            qty INTEGER NOT NULL,
            unit_cost REAL NOT NULL,
            FOREIGN KEY (purchase_id) REFERENCES purchases(id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('asset','liability','equity','revenue','expense')),
            parent_id INTEGER,
            FOREIGN KEY (parent_id) REFERENCES accounts(id))''')
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
            credit REAL NOT NULL DEFAULT 0,
            FOREIGN KEY (entry_id) REFERENCES journal_entries(id),
            FOREIGN KEY (account_id) REFERENCES accounts(id))''')
        # جداول الوحدات الجديدة
        cursor.execute('''CREATE TABLE IF NOT EXISTS vat_settings (id INTEGER PRIMARY KEY, default_rate REAL DEFAULT 0.15, is_enabled INTEGER DEFAULT 1)''')
        cursor.execute("INSERT OR IGNORE INTO vat_settings (id, default_rate, is_enabled) VALUES (1, 0.15, 1)")
        cursor.execute('''CREATE TABLE IF NOT EXISTS fixed_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            purchase_date TEXT NOT NULL,
            purchase_cost REAL NOT NULL,
            salvage_value REAL DEFAULT 0,
            useful_life_years INTEGER NOT NULL,
            depreciation_method TEXT DEFAULT 'straight_line',
            current_value REAL,
            accumulated_depreciation REAL DEFAULT 0,
            status TEXT DEFAULT 'active',
            notes TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS depreciation_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            period INTEGER,
            notes TEXT,
            FOREIGN KEY (asset_id) REFERENCES fixed_assets(id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS warehouses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            location TEXT,
            is_main INTEGER DEFAULT 0)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS warehouse_stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
            UNIQUE(warehouse_id, product_name))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS warehouse_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_warehouse_id INTEGER,
            to_warehouse_id INTEGER,
            product_name TEXT NOT NULL,
            qty INTEGER NOT NULL,
            transfer_date TEXT DEFAULT (datetime('now','localtime')),
            notes TEXT)''')
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
        cursor.execute('''CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            check_in TEXT,
            check_out TEXT,
            status TEXT DEFAULT 'present',
            FOREIGN KEY (employee_id) REFERENCES employees(id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS payroll (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            month INTEGER,
            year INTEGER,
            base_salary REAL,
            bonuses REAL DEFAULT 0,
            deductions REAL DEFAULT 0,
            net_salary REAL,
            paid INTEGER DEFAULT 0,
            payment_date TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS leaves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            leave_type TEXT,
            start_date TEXT,
            end_date TEXT,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (employee_id) REFERENCES employees(id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS bom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            component_name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT DEFAULT 'قطعة',
            FOREIGN KEY (product_name) REFERENCES products(name),
            FOREIGN KEY (component_name) REFERENCES products(name))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS production_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT UNIQUE,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT DEFAULT 'planned',
            start_date TEXT,
            completion_date TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            notes TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS production_consumption (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            component_name TEXT NOT NULL,
            planned_qty REAL NOT NULL,
            actual_qty REAL,
            FOREIGN KEY (order_id) REFERENCES production_orders(id))''')
        conn.commit()
    finally:
        conn.close()
    create_default_accounts()
    create_default_warehouse()

def create_default_accounts():
    defaults = [(1, 'الصندوق', 'asset', None), (2, 'العملاء', 'asset', None),
                (3, 'المخزون', 'asset', None), (4, 'المبيعات', 'revenue', None),
                (5, 'الموردين', 'liability', None), (6, 'رأس المال', 'equity', None),
                (7, 'مصروف الإهلاك', 'expense', None), (8, 'مجمع الإهلاك', 'asset', None)]
    conn = get_conn()
    try:
        cursor = conn.cursor()
        for code, name, type_, parent_id in defaults:
            cursor.execute("SELECT id FROM accounts WHERE code = ?", (code,))
            if cursor.fetchone() is None:
                cursor.execute("INSERT INTO accounts (id, code, name, type, parent_id) VALUES (?,?,?,?,?)",
                               (code, code, name, type_, parent_id))
        conn.commit()
    finally:
        conn.close()

def create_default_warehouse():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM warehouses")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO warehouses (name, location, is_main) VALUES (?,?,?)", ('المستودع الرئيسي', 'الافتراضي', 1))
        conn.commit()
    finally:
        conn.close()

init_db()

# ============================================================
#                         الدوال الأساسية
# ============================================================

def add_product(name, price, stock, vat_rate=0.0):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO products (name, price, stock, vat_rate) VALUES (?,?,?,?)", (name, price, stock, vat_rate))
        conn.commit()
        record_movement(name, stock, 'in', 'مخزون أولي')
    finally:
        conn.close()

def get_all_products():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, price, stock, vat_rate FROM products ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def update_product(product_id, name, price):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET name=?, price=? WHERE id=?", (name, price, product_id))
        conn.commit()
    finally:
        conn.close()

def delete_product(product_id):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM products WHERE id=?", (product_id,))
        row = cursor.fetchone()
        if row:
            pname = row['name']
            cursor.execute("DELETE FROM inventory_movements WHERE product_name=?", (pname,))
            cursor.execute("DELETE FROM sales WHERE product_name=?", (pname,))
            cursor.execute("DELETE FROM purchase_items WHERE product_name=?", (pname,))
            cursor.execute("DELETE FROM warehouse_stock WHERE product_name=?", (pname,))
            cursor.execute("DELETE FROM bom WHERE product_name=? OR component_name=?", (pname, pname))
            cursor.execute("DELETE FROM products WHERE id=?", (product_id,))
            conn.commit()
    finally:
        conn.close()

def update_stock(product_name, qty_change, movement_type, notes=""):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        if movement_type == 'in':
            cursor.execute("UPDATE products SET stock = stock + ? WHERE name=?", (qty_change, product_name))
        else:
            cursor.execute("UPDATE products SET stock = stock - ? WHERE name=?", (qty_change, product_name))
        conn.commit()
        record_movement(product_name, qty_change, movement_type, notes)
    finally:
        conn.close()

def record_movement(product_name, qty, movement_type, notes=""):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO inventory_movements (product_name, qty, movement_type, notes) VALUES (?,?,?,?)",
                       (product_name, qty, movement_type, notes))
        conn.commit()
    finally:
        conn.close()

def add_sale(product_name, qty, total, vat_amount=0, vat_rate=0):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sales (product_name, qty, total, vat_amount, vat_rate) VALUES (?,?,?,?,?)",
                       (product_name, qty, total, vat_amount, vat_rate))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def get_low_stock(threshold=5):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, price, stock FROM products WHERE stock <= ? ORDER BY stock", (threshold,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_sales_summary():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total_sales, COALESCE(SUM(total),0) as total_revenue FROM sales")
        row = cursor.fetchone()
        return {'total_sales': row['total_sales'], 'total_revenue': row['total_revenue']}
    finally:
        conn.close()

# العملاء
def add_customer(name, phone, address):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO customers (name, phone, address, balance) VALUES (?,?,?,0)", (name, phone, address))
        conn.commit()
    finally:
        conn.close()

def get_all_customers():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, phone, address, balance FROM customers ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_customer_statement(customer_id):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, date, type, amount, reference_id, notes FROM customer_transactions WHERE customer_id=? ORDER BY date DESC", (customer_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def add_customer_transaction(customer_id, type_, amount, reference_id=None, notes=""):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO customer_transactions (customer_id, type, amount, reference_id, notes) VALUES (?,?,?,?,?)",
                       (customer_id, type_, amount, reference_id, notes))
        if type_ == 'sale':
            cursor.execute("UPDATE customers SET balance = balance + ? WHERE id=?", (amount, customer_id))
        else:
            cursor.execute("UPDATE customers SET balance = balance - ? WHERE id=?", (amount, customer_id))
        conn.commit()
    finally:
        conn.close()

def receive_payment(customer_id, amount, notes=""):
    add_customer_transaction(customer_id, 'payment', amount, None, notes)
    post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f"تحصيل دفعة من عميل {customer_id}", 'customer_payment', customer_id,
               [{'account_id': 1, 'debit': amount, 'credit': 0}, {'account_id': 2, 'debit': 0, 'credit': amount}])

# الموردين والمشتريات
def add_supplier(name, phone):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO suppliers (name, phone, balance) VALUES (?,?,0)", (name, phone))
        conn.commit()
    finally:
        conn.close()

def get_all_suppliers():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, phone, balance FROM suppliers ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def add_purchase(supplier_id, items):
    total = sum(item['qty'] * item['unit_cost'] for item in items)
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO purchases (supplier_id, total) VALUES (?,?)", (supplier_id, total))
        purchase_id = cursor.lastrowid
        for item in items:
            pname, qty, cost = item['product_name'], item['qty'], item['unit_cost']
            cursor.execute("INSERT INTO purchase_items (purchase_id, product_name, qty, unit_cost) VALUES (?,?,?,?)", (purchase_id, pname, qty, cost))
            cursor.execute("UPDATE products SET stock = stock + ? WHERE name=?", (qty, pname))
            record_movement(pname, qty, 'in', f'شراء فاتورة {purchase_id}')
        cursor.execute("UPDATE suppliers SET balance = balance + ? WHERE id=?", (total, supplier_id))
        conn.commit()
        post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f"فاتورة شراء رقم {purchase_id}", 'purchase', purchase_id,
                   [{'account_id': 3, 'debit': total, 'credit': 0}, {'account_id': 5, 'debit': 0, 'credit': total}])
        return purchase_id
    finally:
        conn.close()

def pay_supplier(supplier_id, amount, notes=""):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE suppliers SET balance = balance - ? WHERE id=?", (amount, supplier_id))
        conn.commit()
    finally:
        conn.close()
    post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f"دفع للمورد {supplier_id}", 'supplier_payment', supplier_id,
               [{'account_id': 5, 'debit': amount, 'credit': 0}, {'account_id': 1, 'debit': 0, 'credit': amount}])

def add_sale_with_customer(product_name, qty, total, vat_amount, vat_rate, customer_id=None):
    sale_id = add_sale(product_name, qty, total, vat_amount, vat_rate)
    if customer_id:
        add_customer_transaction(customer_id, 'sale', total, sale_id, f'فاتورة بيع {product_name}')
        post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f"بيع آجل - فاتورة {sale_id}", 'sale', sale_id,
                   [{'account_id': 2, 'debit': total, 'credit': 0}, {'account_id': 4, 'debit': 0, 'credit': total}])
    else:
        post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f"بيع نقدي - فاتورة {sale_id}", 'sale', sale_id,
                   [{'account_id': 1, 'debit': total, 'credit': 0}, {'account_id': 4, 'debit': 0, 'credit': total}])
    return sale_id

# المحاسبة
def create_account(code, name, type, parent_id=None):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO accounts (code, name, type, parent_id) VALUES (?,?,?,?)", (code, name, type, parent_id))
        conn.commit()
    finally:
        conn.close()

def get_accounts_tree():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, code, name, type, parent_id FROM accounts ORDER BY code")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_account_balance(account_id):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT type FROM accounts WHERE id=?", (account_id,))
        row = cursor.fetchone()
        if not row:
            return 0.0
        acc_type = row['type']
        cursor.execute("SELECT COALESCE(SUM(debit),0) as d, COALESCE(SUM(credit),0) as c FROM journal_details WHERE account_id=?", (account_id,))
        sums = cursor.fetchone()
        debit, credit = sums['d'], sums['c']
        return (debit - credit) if acc_type in ('asset', 'expense') else (credit - debit)
    finally:
        conn.close()

def post_entry(date, description, ref_type, ref_id, details):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO journal_entries (date, description, reference_type, reference_id) VALUES (?,?,?,?)", (date, description, ref_type, ref_id))
        entry_id = cursor.lastrowid
        for d in details:
            cursor.execute("INSERT INTO journal_details (entry_id, account_id, debit, credit) VALUES (?,?,?,?)", (entry_id, d['account_id'], d['debit'], d['credit']))
        conn.commit()
    finally:
        conn.close()

def get_all_journal_entries():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT je.id, je.date, je.description, je.reference_type, je.reference_id,
                   jd.account_id, a.name as account_name, jd.debit, jd.credit
            FROM journal_entries je
            JOIN journal_details jd ON je.id = jd.entry_id
            JOIN accounts a ON jd.account_id = a.id
            ORDER BY je.date DESC""")
        rows = cursor.fetchall()
        entries = {}
        for row in rows:
            eid = row['id']
            if eid not in entries:
                entries[eid] = {'id': eid, 'date': row['date'], 'description': row['description'], 'reference_type': row['reference_type'], 'reference_id': row['reference_id'], 'details': []}
            entries[eid]['details'].append({'account_name': row['account_name'], 'debit': row['debit'], 'credit': row['credit']})
        return list(entries.values())
    finally:
        conn.close()

# الوحدات الجديدة (مختصرة)
# VAT
def get_vat_settings():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT default_rate, is_enabled FROM vat_settings WHERE id=1")
        row = cursor.fetchone()
        return {'default_rate': row['default_rate'], 'is_enabled': row['is_enabled']}
    finally:
        conn.close()

def update_vat_settings(rate, enabled):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE vat_settings SET default_rate=?, is_enabled=? WHERE id=1", (rate, enabled))
        conn.commit()
    finally:
        conn.close()

# الأصول الثابتة
def add_asset(name, purchase_date, cost, salvage, life):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO fixed_assets (name, purchase_date, purchase_cost, salvage_value, useful_life_years, current_value) VALUES (?,?,?,?,?,?)",
                       (name, purchase_date, cost, salvage, life, cost))
        conn.commit()
    finally:
        conn.close()

def get_all_assets():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM fixed_assets ORDER BY purchase_date DESC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def calculate_depreciation(asset):
    return (asset['purchase_cost'] - asset['salvage_value']) / asset['useful_life_years']

# المستودعات
def add_warehouse(name, location, is_main=False):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO warehouses (name, location, is_main) VALUES (?,?,?)", (name, location, 1 if is_main else 0))
        conn.commit()
    finally:
        conn.close()

def get_all_warehouses():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, location, is_main FROM warehouses ORDER BY is_main DESC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def update_warehouse_stock(wh_id, product_name, qty_change):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO warehouse_stock (warehouse_id, product_name, stock) VALUES (?,?,?) ON CONFLICT(warehouse_id, product_name) DO UPDATE SET stock = stock + ?",
                       (wh_id, product_name, qty_change, qty_change))
        conn.commit()
    finally:
        conn.close()

# الموارد البشرية (مختصرة للمساحة)
def add_employee(name, position, department, hire_date, salary, phone, email):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO employees (name, position, department, hire_date, salary, phone, email) VALUES (?,?,?,?,?,?,?)",
                       (name, position, department, hire_date, salary, phone, email))
        conn.commit()
    finally:
        conn.close()

def get_all_employees():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, position, department, salary, status FROM employees ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def record_checkin(employee_id):
    today = date.today().isoformat()
    now = datetime.now().strftime('%H:%M:%S')
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO attendance (employee_id, date, check_in) VALUES (?,?,?) ON CONFLICT DO UPDATE SET check_in=?", (employee_id, today, now, now))
        conn.commit()
    finally:
        conn.close()

# الإنتاج (BOM)
def add_bom(product, component, qty):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO bom (product_name, component_name, quantity) VALUES (?,?,?)", (product, component, qty))
        conn.commit()
    finally:
        conn.close()

def get_bom(product):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT component_name, quantity FROM bom WHERE product_name=?", (product,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def create_production_order(product, qty):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        order_number = f"PO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        cursor.execute("INSERT INTO production_orders (order_number, product_name, quantity) VALUES (?,?,?)", (order_number, product, qty))
        order_id = cursor.lastrowid
        for comp in get_bom(product):
            cursor.execute("INSERT INTO production_consumption (order_id, component_name, planned_qty) VALUES (?,?,?)", (order_id, comp['component_name'], comp['quantity'] * qty))
        conn.commit()
        return order_id
    finally:
        conn.close()

def get_production_orders():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM production_orders ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def complete_production(order_id):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT product_name, quantity FROM production_orders WHERE id=?", (order_id,))
        order = cursor.fetchone()
        if order:
            update_stock(order['product_name'], order['quantity'], 'in', f'إنتاج أمر {order_id}')
            cursor.execute("UPDATE production_orders SET status='completed', completion_date=? WHERE id=?", (date.today().isoformat(), order_id))
            conn.commit()
    finally:
        conn.close()

# ============================================================
#                         واجهة المستخدم الرئيسية
# ============================================================
st.set_page_config(page_title="نظام ERP المتكامل", layout="wide")
st.title("🏢 نظام ERP المتكامل – المسرحية المحاسبية")
st.caption("إدارة متكاملة: المنتجات، المبيعات، العملاء، الموردين، المحاسبة، الضريبة، الأصول، المستودعات، الموارد البشرية، الإنتاج")

menu = st.sidebar.radio("القائمة الرئيسية", 
    ["📦 المنتجات", "🛒 الكاشير", "👥 العملاء", "📦 الموردين", "📊 المحاسبة", "💰 الضريبة (VAT)", "🏭 الأصول الثابتة", "🏚️ المستودعات", "👨‍💼 الموارد البشرية", "🏭 الإنتاج (BOM)", "📈 التقارير المتقدمة"])

# 1. المنتجات
if menu == "📦 المنتجات":
    st.header("إدارة المنتجات")
    products = get_all_products()
    low = get_low_stock(5)
    col1, col2 = st.columns(2)
    col1.metric("إجمالي المنتجات", len(products))
    col2.metric("منخفضة المخزون (≤5)", len(low))
    with st.expander("➕ إضافة منتج"):
        with st.form("add_p"):
            name = st.text_input("الاسم")
            price = st.number_input("السعر", min_value=0.0)
            stock = st.number_input("المخزون", min_value=0)
            vat = st.number_input("نسبة الضريبة (%)", min_value=0.0, max_value=100.0, step=0.5)
            if st.form_submit_button("إضافة"):
                add_product(name, price, stock, vat/100)
                st.rerun()
    if products:
        for p in products:
            col1, col2, col3, col4, col5 = st.columns([2,1,1,1,1])
            col1.write(f"**{p['name']}**")
            col2.write(f"{p['price']:.2f}")
            col3.write(f"{p['stock']}")
            col4.write(f"{p['vat_rate']*100:.0f}%")
            if col5.button("حذف", key=f"del_{p['id']}"):
                delete_product(p['id'])
                st.rerun()

# 2. الكاشير
elif menu == "🛒 الكاشير":
    st.header("واجهة البيع")
    if 'cart' not in st.session_state: st.session_state.cart = []
    products = {p['name']: p for p in get_all_products()}
    customers = get_all_customers()
    cust_options = {c['id']: c['name'] for c in customers}
    cust_options[None] = "بدون عميل (نقدي)"
    selected_cust = st.selectbox("العميل", list(cust_options.keys()), format_func=lambda x: cust_options[x])
    col1, col2 = st.columns([2,1])
    with col1:
        prod_names = list(products.keys())
        prod = st.selectbox("المنتج", prod_names)
        qty = st.number_input("الكمية", min_value=1, step=1)
        if st.button("إضافة للسلة"):
            p = products[prod]
            if p['stock'] >= qty:
                st.session_state.cart.append({"name": prod, "price": p['price'], "qty": qty, "vat": p['vat_rate']})
                st.rerun()
            else:
                st.error("المخزون غير كافٍ")
    with col2:
        if st.session_state.cart:
            total = 0
            for i, item in enumerate(st.session_state.cart):
                subtotal = item['price'] * item['qty']
                vat_amt = subtotal * item['vat']
                total += subtotal + vat_amt
                st.write(f"{item['name']} x{item['qty']} = {subtotal:.2f} + ضريبة {item['vat']*100:.0f}% = {subtotal+vat_amt:.2f}")
                if st.button(f"حذف", key=f"rem_{i}"):
                    st.session_state.cart.pop(i)
                    st.rerun()
            st.metric("الإجمالي", f"{total:.2f}")
            if st.button("إتمام البيع"):
                for item in st.session_state.cart:
                    subtotal = item['price'] * item['qty']
                    vat_amt = subtotal * item['vat']
                    update_stock(item['name'], item['qty'], 'out', f'بيع')
                    add_sale_with_customer(item['name'], item['qty'], subtotal+vat_amt, vat_amt, item['vat'], selected_cust if selected_cust!=None else None)
                st.session_state.cart = []
                st.success("تم البيع")
                st.rerun()
        else:
            st.info("السلة فارغة")

# 3. العملاء (مختصر)
elif menu == "👥 العملاء":
    st.header("العملاء والديون")
    tab1, tab2 = st.tabs(["قائمة العملاء", "إضافة عميل"])
    with tab1:
        for c in get_all_customers():
            with st.expander(f"{c['name']} - الرصيد: {c['balance']:.2f}"):
                st.write(f"📞 {c['phone']} | 🏠 {c['address']}")
                if st.button(f"كشف حساب", key=f"stmt_{c['id']}"):
                    stmt = get_customer_statement(c['id'])
                    st.dataframe(stmt)
    with tab2:
        with st.form("new_cust"):
            name = st.text_input("الاسم")
            phone = st.text_input("الجوال")
            address = st.text_input("العنوان")
            if st.form_submit_button("إضافة"):
                add_customer(name, phone, address)
                st.rerun()

# 4. الموردين (مختصر)
elif menu == "📦 الموردين":
    st.header("الموردين والمشتريات")
    tab1, tab2 = st.tabs(["الموردين", "فاتورة شراء"])
    with tab1:
        for s in get_all_suppliers():
            st.write(f"**{s['name']}** - 📞 {s['phone']} - الرصيد: {s['balance']:.2f}")
    with tab2:
        suppliers = get_all_suppliers()
        if suppliers:
            sup_map = {s['id']: s['name'] for s in suppliers}
            sup = st.selectbox("المورد", list(sup_map.keys()), format_func=lambda x: sup_map[x])
            if 'purchase_items' not in st.session_state: st.session_state.purchase_items = []
            prods = get_all_products()
            pnames = [p['name'] for p in prods]
            col1, col2, col3 = st.columns(3)
            with col1: pn = st.selectbox("المنتج", pnames, key="pname")
            with col2: qty = st.number_input("الكمية", min_value=1, key="pqty")
            with col3: cost = st.number_input("سعر الشراء", min_value=0.01, key="pcost")
            if st.button("إضافة صنف"):
                st.session_state.purchase_items.append({"product_name": pn, "qty": qty, "unit_cost": cost})
                st.rerun()
            if st.session_state.purchase_items:
                total = 0
                for idx, it in enumerate(st.session_state.purchase_items):
                    st.write(f"{it['product_name']} - {it['qty']} × {it['unit_cost']} = {it['qty']*it['unit_cost']}")
                    if st.button(f"حذف", key=f"del_pi_{idx}"):
                        st.session_state.purchase_items.pop(idx)
                        st.rerun()
                    total += it['qty']*it['unit_cost']
                st.metric("الإجمالي", f"{total:.2f}")
                if st.button("حفظ الفاتورة"):
                    add_purchase(sup, st.session_state.purchase_items)
                    st.session_state.purchase_items = []
                    st.rerun()

# 5. المحاسبة
elif menu == "📊 المحاسبة":
    st.header("دليل الحسابات والقيود")
    tab1, tab2 = st.tabs(["الحسابات", "القيود"])
    with tab1:
        accs = get_accounts_tree()
        if accs:
            df = pd.DataFrame(accs)
            df['الرصيد'] = df['id'].apply(get_account_balance)
            st.dataframe(df[['code', 'name', 'type', 'الرصيد']])
    with tab2:
        entries = get_all_journal_entries()
        for e in entries:
            with st.expander(f"{e['date']} - {e['description']}"):
                st.dataframe(pd.DataFrame(e['details']))

# 6. الضريبة
elif menu == "💰 الضريبة (VAT)":
    st.header("إعدادات الضريبة")
    settings = get_vat_settings()
    rate = st.number_input("نسبة الضريبة الافتراضية (%)", min_value=0.0, max_value=100.0, value=settings['default_rate']*100) / 100
    enabled = st.checkbox("تفعيل الضريبة", value=settings['is_enabled']==1)
    if st.button("حفظ"):
        update_vat_settings(rate, enabled)
        st.rerun()

# 7. الأصول الثابتة
elif menu == "🏭 الأصول الثابتة":
    st.header("الأصول الثابتة والإهلاك")
    with st.form("add_asset"):
        name = st.text_input("اسم الأصل")
        cost = st.number_input("التكلفة", min_value=0.0)
        salvage = st.number_input("القيمة الخردة", min_value=0.0)
        life = st.number_input("العمر الإنتاجي (سنوات)", min_value=1, step=1)
        if st.form_submit_button("إضافة"):
            add_asset(name, date.today().isoformat(), cost, salvage, life)
            st.rerun()
    assets = get_all_assets()
    for a in assets:
        st.write(f"{a['name']} - التكلفة: {a['purchase_cost']} - القيمة الحالية: {a['current_value']}")
        if st.button(f"حساب الإهلاك", key=f"dep_{a['id']}"):
            dep = calculate_depreciation(a)
            st.info(f"الإهلاك السنوي: {dep:.2f}")

# 8. المستودعات
elif menu == "🏚️ المستودعات":
    st.header("المستودعات")
    with st.form("add_wh"):
        name = st.text_input("اسم المستودع")
        loc = st.text_input("الموقع")
        main = st.checkbox("رئيسي")
        if st.form_submit_button("إضافة"):
            add_warehouse(name, loc, main)
            st.rerun()
    whs = get_all_warehouses()
    for w in whs:
        st.write(f"**{w['name']}** - {w['location']}" + (" (رئيسي)" if w['is_main'] else ""))

# 9. الموارد البشرية
elif menu == "👨‍💼 الموارد البشرية":
    st.header("الموظفون")
    with st.form("add_emp"):
        name = st.text_input("الاسم")
        pos = st.text_input("الوظيفة")
        dept = st.text_input("القسم")
        salary = st.number_input("الراتب", min_value=0.0)
        phone = st.text_input("الجوال")
        email = st.text_input("البريد")
        if st.form_submit_button("إضافة"):
            add_employee(name, pos, dept, date.today().isoformat(), salary, phone, email)
            st.rerun()
    emps = get_all_employees()
    for e in emps:
        with st.expander(f"{e['name']} - {e['position']}"):
            st.write(f"الراتب: {e['salary']} - الحالة: {e['status']}")
            if st.button(f"تسجيل حضور", key=f"checkin_{e['id']}"):
                record_checkin(e['id'])
                st.success("تم تسجيل الحضور")

# 10. الإنتاج
elif menu == "🏭 الإنتاج (BOM)":
    st.header("إدارة الإنتاج")
    tab1, tab2 = st.tabs(["BOM", "أوامر الإنتاج"])
    with tab1:
        prod = st.selectbox("المنتج النهائي", [p['name'] for p in get_all_products()])
        comp = st.selectbox("المكون", [p['name'] for p in get_all_products() if p['name'] != prod])
        qty = st.number_input("الكمية لكل وحدة", min_value=0.1, step=0.1)
        if st.button("إضافة إلى BOM"):
            add_bom(prod, comp, qty)
            st.rerun()
        bom = get_bom(prod)
        if bom:
            st.dataframe(pd.DataFrame(bom))
    with tab2:
        prod_order = st.selectbox("المنتج للإنتاج", [p['name'] for p in get_all_products()])
        order_qty = st.number_input("الكمية", min_value=1, step=1)
        if st.button("إنشاء أمر إنتاج"):
            create_production_order(prod_order, order_qty)
            st.rerun()
        orders = get_production_orders()
        for o in orders:
            st.write(f"{o['order_number']} - {o['product_name']} - {o['quantity']} - {o['status']}")
            if o['status'] == 'planned' and st.button(f"بدء", key=f"start_{o['id']}"):
                st.info("بدء الإنتاج (وهمي) - أكمل يدوياً")

# 11. التقارير المتقدمة
elif menu == "📈 التقارير المتقدمة":
    st.header("تحليلات متقدمة")
    conn = get_conn()
    sales_df = pd.read_sql("SELECT date_time, total FROM sales", conn)
    if not sales_df.empty:
        sales_df['date'] = pd.to_datetime(sales_df['date_time']).dt.date
        daily = sales_df.groupby('date')['total'].sum().reset_index()
        fig = px.line(daily, x='date', y='total', title='المبيعات اليومية')
        st.plotly_chart(fig)
    else:
        st.info("لا توجد مبيعات")
