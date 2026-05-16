import sqlite3
from datetime import datetime, date
import streamlit as st
import pandas as pd
import plotly.express as px
import hashlib
import io
from PIL import Image, ImageDraw, ImageFont
import os

# ============================================================
#                         إعدادات الصفحة
# ============================================================
st.set_page_config(page_title="نظام ERP المتكامل - المسرحية المحاسبية", page_icon="🎭", layout="wide")

# ============================================================
#                         CSS الاحترافي
# ============================================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Cairo', sans-serif; }
    .main { background: linear-gradient(135deg, #f8f9fc 0%, #f0f2f6 100%); }
    .metric-card {
        background: white; border-radius: 28px; padding: 22px 15px; box-shadow: 0 8px 25px rgba(0,0,0,0.05);
        text-align: center; transition: all 0.3s ease; border: 1px solid rgba(106, 13, 173, 0.1);
    }
    .metric-card:hover { transform: translateY(-6px); box-shadow: 0 20px 35px rgba(106, 13, 173, 0.15); border-color: #6a0dad; }
    .metric-card h3 { font-size: 2.2rem; margin: 12px 0; background: linear-gradient(135deg, #6a0dad, #8b5cf6); background-clip: text; -webkit-background-clip: text; color: transparent; }
    .metric-card p { color: #4a5568; font-weight: 600; margin: 0; }
    .stButton > button { background: linear-gradient(135deg, #6a0dad, #8b5cf6); color: white; border-radius: 40px; border: none; padding: 10px 25px; font-weight: 600; transition: all 0.3s ease; width: 100%; }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 10px 25px rgba(106, 13, 173, 0.3); }
    .css-1d391kg { background: linear-gradient(180deg, #0f0f1f, #1a1a2e); border-radius: 0 35px 35px 0; }
    .css-1d391kg .stMarkdown, .css-1d391kg .stSelectbox label { color: #f0f0f0; }
    .dataframe { border-radius: 20px; overflow: hidden; box-shadow: 0 8px 20px rgba(0,0,0,0.05); }
    .dataframe th { background: linear-gradient(135deg, #6a0dad, #8b5cf6); color: white; padding: 12px; }
    .stTabs [data-baseweb="tab"] { background: white; border-radius: 40px; padding: 8px 24px; font-weight: 600; color: #4a5568; border: 1px solid #e2e8f0; }
    .stTabs [aria-selected="true"] { background: linear-gradient(135deg, #6a0dad, #8b5cf6); color: white; }
    .section-title { font-size: 2rem; font-weight: 700; margin-bottom: 30px; border-right: 6px solid #6a0dad; padding-right: 20px; color: #1a1a2e; display: inline-block; }
    .footer { text-align: center; margin-top: 55px; padding: 22px; background: white; border-radius: 50px; color: #4a5568; font-size: 0.85rem; }
    </style>
""", unsafe_allow_html=True)

# ============================================================
#                         قاعدة البيانات
# ============================================================

def get_conn():
    conn = sqlite3.connect('erp.db')
    conn.row_factory = sqlite3.Row
    return conn

def upgrade_database():
    """إضافة أعمدة جديدة للجداول الموجودة"""
    conn = get_conn()
    cursor = conn.cursor()
    # إضافة أعمدة لجدول sales إذا لم تكن موجودة
    for col in ['vat_rate', 'vat_amount', 'returned_qty']:
        try:
            cursor.execute(f"ALTER TABLE sales ADD COLUMN {col} REAL DEFAULT 0")
        except:
            pass
    # إضافة عمود vat_rate لجدول products
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN vat_rate REAL DEFAULT 0.0")
    except:
        pass
    conn.commit()
    conn.close()

def init_db():
    conn = get_conn()
    cursor = conn.cursor()
    
    # جداول النظام الأساسية (مع IF NOT EXISTS)
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
    
    # جدول إعدادات الضريبة (تم إنشاؤه بشكل آمن)
    cursor.execute('''CREATE TABLE IF NOT EXISTS vat_settings (
        id INTEGER PRIMARY KEY,
        default_rate REAL DEFAULT 0.15,
        is_enabled INTEGER DEFAULT 1)''')
    
    # إدراج البيانات الافتراضية فقط إذا كان الجدول فارغاً
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
    
    # جدول المستخدمين (للصلاحيات)
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL)''')
    
    # إضافة المستخدمين الافتراضيين إذا لم يوجد أي مستخدم
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
        cashier_hash = hashlib.sha256("cashier123".encode()).hexdigest()
        accountant_hash = hashlib.sha256("accountant123".encode()).hexdigest()
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)", ('admin', admin_hash, 'admin'))
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)", ('cashier', cashier_hash, 'cashier'))
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?,?,?)", ('accountant', accountant_hash, 'accountant'))
    
    conn.commit()
    conn.close()
    create_default_accounts()
    upgrade_database()

def create_default_accounts():
    """إنشاء الحسابات الافتراضية إذا لم تكن موجودة"""
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

# تهيئة قاعدة البيانات (ستُنشأ فقط إذا لم تكن موجودة)
init_db()

# ============================================================
#                         دوال المصادقة
# ============================================================
def authenticate(username, password):
    conn = get_conn()
    cursor = conn.cursor()
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute("SELECT role FROM users WHERE username=? AND password_hash=?", (username, pwd_hash))
    user = cursor.fetchone()
    conn.close()
    return user['role'] if user else None

# ============================================================
#                         دوال النسخ الاحتياطي
# ============================================================
def backup_database():
    import time
    backup_file = f"backup_erp_{int(time.time())}.db"
    conn = get_conn()
    backup_conn = sqlite3.connect(backup_file)
    conn.backup(backup_conn)
    backup_conn.close()
    conn.close()
    return backup_file

# ============================================================
#                         دوال طباعة الصورة
# ============================================================
def generate_invoice_image(sale_id, customer_name, items, total):
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        font_normal = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        font_title = ImageFont.load_default()
        font_normal = ImageFont.load_default()
    y = 30
    draw.text((50, y), f"فاتورة البيع رقم: {sale_id}", fill='black', font=font_title)
    y += 40
    draw.text((50, y), f"العميل: {customer_name}", fill='black', font=font_normal)
    y += 30
    draw.text((50, y), f"التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}", fill='black', font=font_normal)
    y += 50
    draw.text((50, y), "المنتج", fill='black', font=font_normal)
    draw.text((300, y), "الكمية", fill='black', font=font_normal)
    draw.text((450, y), "السعر", fill='black', font=font_normal)
    draw.text((600, y), "الإجمالي", fill='black', font=font_normal)
    y += 30
    draw.line((50, y, 750, y), fill='black', width=2)
    y += 20
    for item in items:
        draw.text((50, y), item['product'], fill='black', font=font_normal)
        draw.text((300, y), str(item['qty']), fill='black', font=font_normal)
        draw.text((450, y), f"{item['price']:.2f}", fill='black', font=font_normal)
        draw.text((600, y), f"{item['total']:.2f}", fill='black', font=font_normal)
        y += 30
    draw.line((50, y, 750, y), fill='black', width=1)
    y += 20
    draw.text((500, y), f"الإجمالي: {total:.2f}", fill='black', font=font_title)
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes

# ============================================================
#                         الدوال الأساسية (مختصرة)
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

def delete_product(product_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM products WHERE id=?", (product_id,))
    row = cursor.fetchone()
    if row:
        pname = row['name']
        cursor.execute("DELETE FROM inventory_movements WHERE product_name=?", (pname,))
        cursor.execute("DELETE FROM sales WHERE product_name=?", (pname,))
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
    conn.commit()
    record_movement(product_name, qty_change, movement_type, notes)
    conn.close()

def record_movement(product_name, qty, movement_type, notes=""):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO inventory_movements (product_name, qty, movement_type, notes) VALUES (?,?,?,?)", (product_name, qty, movement_type, notes))
    conn.commit()
    conn.close()

def add_sale(product_name, qty, total, vat_amount=0, vat_rate=0):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO sales (product_name, qty, total, vat_amount, vat_rate) VALUES (?,?,?,?,?)", (product_name, qty, total, vat_amount, vat_rate))
    conn.commit()
    sale_id = cursor.lastrowid
    conn.close()
    return sale_id

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

def get_customer_statement(customer_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT date, type, amount, notes FROM customer_transactions WHERE customer_id=? ORDER BY date DESC", (customer_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_customer_transaction(customer_id, type_, amount, reference_id=None, notes=""):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO customer_transactions (customer_id, type, amount, reference_id, notes) VALUES (?,?,?,?,?)", (customer_id, type_, amount, reference_id, notes))
    if type_ == 'sale':
        cursor.execute("UPDATE customers SET balance = balance + ? WHERE id=?", (amount, customer_id))
    elif type_ == 'return':
        cursor.execute("UPDATE customers SET balance = balance - ? WHERE id=?", (amount, customer_id))
    else:
        cursor.execute("UPDATE customers SET balance = balance - ? WHERE id=?", (amount, customer_id))
    conn.commit()
    conn.close()

def receive_payment(customer_id, amount, notes=""):
    add_customer_transaction(customer_id, 'payment', amount, None, notes)
    post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f"تحصيل دفعة من عميل", 'payment', customer_id,
               [{'account_id': 1, 'debit': amount, 'credit': 0}, {'account_id': 2, 'debit': 0, 'credit': amount}])

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
    total = sum(item['qty'] * item['unit_cost'] for item in items)
    conn = get_conn()
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
    conn.close()
    return purchase_id

def add_sale_with_customer(product_name, qty, total, vat_amount, vat_rate, customer_id=None):
    sale_id = add_sale(product_name, qty, total, vat_amount, vat_rate)
    update_stock(product_name, qty, 'out', f'بيع')
    if customer_id:
        add_customer_transaction(customer_id, 'sale', total, sale_id, f'فاتورة بيع {product_name}')
        post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f"بيع آجل - فاتورة {sale_id}", 'sale', sale_id,
                   [{'account_id': 2, 'debit': total, 'credit': 0}, {'account_id': 4, 'debit': 0, 'credit': total}])
    else:
        post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f"بيع نقدي - فاتورة {sale_id}", 'sale', sale_id,
                   [{'account_id': 1, 'debit': total, 'credit': 0}, {'account_id': 4, 'debit': 0, 'credit': total}])
    return sale_id

def post_entry(date, description, ref_type, ref_id, details):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO journal_entries (date, description, reference_type, reference_id) VALUES (?,?,?,?)", (date, description, ref_type, ref_id))
    entry_id = cursor.lastrowid
    for d in details:
        cursor.execute("INSERT INTO journal_details (entry_id, account_id, debit, credit) VALUES (?,?,?,?)", (entry_id, d['account_id'], d['debit'], d['credit']))
    conn.commit()
    conn.close()

def get_account_balance(account_id):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(SUM(debit),0) - COALESCE(SUM(credit),0) FROM journal_details WHERE account_id=?", (account_id,))
    bal = cursor.fetchone()[0]
    conn.close()
    return bal

def get_accounts_tree():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, code, name, type FROM accounts ORDER BY code")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_journal_entries():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT je.id, je.date, je.description, je.reference_type, je.reference_id,
               a.name as account_name, jd.debit, jd.credit
        FROM journal_entries je
        JOIN journal_details jd ON je.id = jd.entry_id
        JOIN accounts a ON jd.account_id = a.id
        ORDER BY je.date DESC, je.id DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    entries = {}
    for row in rows:
        eid = row['id']
        if eid not in entries:
            entries[eid] = {'date': row['date'], 'description': row['description'], 'reference': f"{row['reference_type']} - {row['reference_id']}" if row['reference_id'] else '', 'details': []}
        entries[eid]['details'].append({'account': row['account_name'], 'debit': row['debit'], 'credit': row['credit']})
    return entries

def advanced_report():
    conn = get_conn()
    sales_df = pd.read_sql("SELECT date_time, total FROM sales", conn)
    conn.close()
    if not sales_df.empty:
        sales_df['date'] = pd.to_datetime(sales_df['date_time']).dt.date
        daily = sales_df.groupby('date')['total'].sum().reset_index()
        fig = px.line(daily, x='date', y='total', title='المبيعات اليومية', markers=True, color_discrete_sequence=['#6a0dad'])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("لا توجد بيانات مبيعات")

# مرتجعات المبيعات
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
        invoices[inv_id]['items'].append({'product': row['product_name'], 'qty': row['qty'], 'returned': row['returned_qty'], 'total': row['total']})
    return list(invoices.values())

def process_return(sale_id, product_name, return_qty):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT qty, total, vat_amount, vat_rate FROM sales WHERE id=? AND product_name=?", (sale_id, product_name))
        sale = cursor.fetchone()
        if not sale: raise ValueError("البيع غير موجود")
        if return_qty <= 0: raise ValueError("كمية المرتجع يجب أن تكون أكبر من صفر")
        if return_qty > sale['qty']: raise ValueError("كمية المرتجع أكبر من الكمية المباعة")
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
#                         واجهة المستخدم مع المصادقة
# ============================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.role = None

if not st.session_state.authenticated:
    st.title("تسجيل الدخول")
    username = st.text_input("اسم المستخدم")
    password = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        role = authenticate(username, password)
        if role:
            st.session_state.authenticated = True
            st.session_state.role = role
            st.rerun()
        else:
            st.error("بيانات غير صحيحة")
    st.stop()

# الشريط الجانبي
st.sidebar.markdown("<h2 style='text-align:center; color:white;'>🎭 المسرحية المحاسبية</h2>", unsafe_allow_html=True)
st.sidebar.markdown(f"**مرحباً {st.session_state.role}**")
st.sidebar.markdown("---")

menu_options = ["🏠 لوحة التحكم", "📦 المنتجات", "🛒 الكاشير", "👥 العملاء", "📦 الموردين",
                "📊 المحاسبة", "💰 الضريبة (VAT)", "🏭 الأصول الثابتة", "🏚️ المستودعات",
                "👨‍💼 الموارد البشرية", "🏭 الإنتاج (BOM)", "📈 التقارير المتقدمة", "🔄 مرتجعات المبيعات", "⚙️ إعدادات النظام"]

# تصفية القائمة حسب الصلاحيات
allowed = []
if st.session_state.role == 'admin':
    allowed = menu_options
elif st.session_state.role == 'cashier':
    allowed = ["🏠 لوحة التحكم", "📦 المنتجات", "🛒 الكاشير", "📈 التقارير المتقدمة", "🔄 مرتجعات المبيعات"]
elif st.session_state.role == 'accountant':
    allowed = ["🏠 لوحة التحكم", "👥 العملاء", "📦 الموردين", "📊 المحاسبة", "💰 الضريبة (VAT)", "🏭 الأصول الثابتة", "📈 التقارير المتقدمة"]

menu = st.sidebar.radio("القائمة الرئيسية", allowed)
st.sidebar.markdown("---")
if st.sidebar.button("تسجيل الخروج"):
    st.session_state.authenticated = False
    st.rerun()
st.sidebar.caption("© 2025 - جميع الحقوق محفوظة")

# ========== الأقسام الرئيسية ==========
if menu == "🏠 لوحة التحكم":
    st.markdown("<div class='section-title'>🏠 لوحة القيادة</div>", unsafe_allow_html=True)
    products = get_all_products()
    sales_sum = get_sales_summary()
    low_stock = get_low_stock(5)
    customers = get_all_customers()
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(f"<div class='metric-card'><p>📦 إجمالي المنتجات</p><h3>{len(products)}</h3></div>", unsafe_allow_html=True)
    with col2: st.markdown(f"<div class='metric-card'><p>💰 إجمالي المبيعات</p><h3>{sales_sum['total_revenue']:,.0f}</h3></div>", unsafe_allow_html=True)
    with col3: st.markdown(f"<div class='metric-card'><p>⚠️ مخزون منخفض</p><h3>{len(low_stock)}</h3></div>", unsafe_allow_html=True)
    with col4: st.markdown(f"<div class='metric-card'><p>👥 العملاء</p><h3>{len(customers)}</h3></div>", unsafe_allow_html=True)
    st.markdown("---")
    if low_stock: st.warning("⚠️ المنتجات منخفضة المخزون: " + ", ".join([p['name'] for p in low_stock]))
    else: st.success("✅ جميع المنتجات بمخزون جيد")

elif menu == "📦 المنتجات":
    if st.session_state.role not in ['admin', 'cashier']: st.error("غير مصرح")
    else:
        st.markdown("<div class='section-title'>📦 إدارة المنتجات</div>", unsafe_allow_html=True)
        with st.expander("➕ إضافة منتج جديد"):
            with st.form("add_prod"):
                name = st.text_input("اسم المنتج")
                price = st.number_input("السعر", min_value=0.0, step=1.0)
                stock = st.number_input("المخزون الأولي", min_value=0, step=1)
                vat = st.number_input("نسبة الضريبة (%)", min_value=0.0, max_value=100.0, step=0.5, value=0.0)
                if st.form_submit_button("إضافة"):
                    add_product(name, price, stock, vat/100)
                    st.success(f"تم إضافة {name}")
                    st.rerun()
        products = get_all_products()
        if products:
            df = pd.DataFrame(products)
            st.dataframe(df[['name', 'price', 'stock', 'vat_rate']], use_container_width=True)
            for p in products:
                cols = st.columns([3,1,1])
                cols[0].write(f"**{p['name']}** - السعر: {p['price']:.2f} - المخزون: {p['stock']} - ضريبة: {p['vat_rate']*100:.0f}%")
                if cols[1].button("تعديل المخزون", key=f"stock_{p['id']}"):
                    st.session_state.stock_prod = p
                if cols[2].button("حذف", key=f"del_{p['id']}"):
                    delete_product(p['id'])
                    st.rerun()
            if 'stock_prod' in st.session_state:
                p = st.session_state.stock_prod
                with st.form("up_stock"):
                    change = st.number_input(f"تغيير مخزون {p['name']} (موجب للإضافة، سالب للسحب)", step=1)
                    if st.form_submit_button("تطبيق"):
                        update_stock(p['name'], abs(change), 'in' if change>0 else 'out', "تعديل يدوي")
                        del st.session_state.stock_prod
                        st.rerun()

elif menu == "🛒 الكاشير":
    if st.session_state.role not in ['admin', 'cashier']: st.error("غير مصرح")
    else:
        st.markdown("<div class='section-title'>🛒 واجهة البيع</div>", unsafe_allow_html=True)
        if 'cart' not in st.session_state: st.session_state.cart = []
        products = {p['name']: p for p in get_all_products()}
        customers = get_all_customers()
        cust_opts = {c['id']: c['name'] for c in customers}
        cust_opts[None] = "بدون عميل (نقدي)"
        selected_cust = st.selectbox("اختر العميل", list(cust_opts.keys()), format_func=lambda x: cust_opts[x])
        col1, col2 = st.columns([2,1])
        with col1:
            prod_names = list(products.keys())
            prod = st.selectbox("المنتج", prod_names)
            qty = st.number_input("الكمية", min_value=1, step=1)
            if st.button("➕ إضافة إلى السلة"):
                p = products[prod]
                if p['stock'] >= qty:
                    st.session_state.cart.append({"name": prod, "price": p['price'], "qty": qty, "vat": p['vat_rate']})
                    st.rerun()
                else: st.error("المخزون غير كافٍ")
        with col2:
            if st.session_state.cart:
                total = 0
                for i, item in enumerate(st.session_state.cart):
                    sub = item['price'] * item['qty']
                    vat_amt = sub * item['vat']
                    total += sub + vat_amt
                    st.write(f"**{item['name']}** x{item['qty']} = {sub:.2f} + ضريبة {item['vat']*100:.0f}% = {sub+vat_amt:.2f}")
                    if st.button(f"🗑️ حذف", key=f"rem_{i}"):
                        st.session_state.cart.pop(i)
                        st.rerun()
                st.metric("الإجمالي", f"{total:.2f} ﷼")
                if st.button("✅ إتمام البيع"):
                    sale_id = None
                    items_inv = []
                    total_inv = 0
                    for item in st.session_state.cart:
                        sub = item['price'] * item['qty']
                        vat_amt = sub * item['vat']
                        sale_id = add_sale_with_customer(item['name'], item['qty'], sub+vat_amt, vat_amt, item['vat'], selected_cust if selected_cust!=None else None)
                        items_inv.append({'product': item['name'], 'qty': item['qty'], 'price': item['price'], 'total': sub+vat_amt})
                        total_inv += sub+vat_amt
                    customer_name = cust_opts[selected_cust] if selected_cust else "نقدي"
                    img_bytes = generate_invoice_image(sale_id, customer_name, items_inv, total_inv)
                    st.download_button("📄 تحميل الفاتورة (صورة)", img_bytes, file_name=f"invoice_{sale_id}.png", mime="image/png")
                    st.session_state.cart = []
                    st.success("تم البيع بنجاح")
                    st.rerun()
            else: st.info("السلة فارغة")

elif menu == "👥 العملاء":
    st.markdown("<div class='section-title'>👥 العملاء والديون</div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 قائمة العملاء", "➕ إضافة عميل"])
    with tab1:
        customers = get_all_customers()
        if customers:
            for c in customers:
                with st.expander(f"{c['name']} - الرصيد: {c['balance']:.2f}"):
                    st.write(f"📞 {c['phone']} | 🏠 {c['address']}")
                    if st.button(f"📜 كشف حساب", key=f"stmt_{c['id']}"):
                        stmt = get_customer_statement(c['id'])
                        if stmt: st.dataframe(stmt)
                        else: st.info("لا توجد معاملات")
                    amt = st.number_input("مبلغ التحصيل", key=f"pay_{c['id']}", min_value=0.01, step=100.0)
                    if st.button(f"💰 تحصيل", key=f"rec_{c['id']}"):
                        receive_payment(c['id'], amt, "تحصيل يدوي")
                        st.rerun()
        else: st.info("لا يوجد عملاء")
    with tab2:
        with st.form("add_cust"):
            name = st.text_input("الاسم")
            phone = st.text_input("الجوال")
            address = st.text_input("العنوان")
            if st.form_submit_button("إضافة"):
                add_customer(name, phone, address)
                st.rerun()

elif menu == "📦 الموردين":
    st.markdown("<div class='section-title'>📦 الموردين والمشتريات</div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 الموردين", "➕ فاتورة شراء"])
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
            with col1: pn = st.selectbox("المنتج", pnames)
            with col2: qt = st.number_input("الكمية", min_value=1, step=1)
            with col3: cost = st.number_input("سعر الشراء", min_value=0.01, step=0.01)
            if st.button("➕ إضافة صنف"):
                st.session_state.purchase_items.append({"product_name": pn, "qty": qt, "unit_cost": cost})
                st.rerun()
            if st.session_state.purchase_items:
                tot = 0
                for idx, it in enumerate(st.session_state.purchase_items):
                    st.write(f"{it['product_name']} - {it['qty']} × {it['unit_cost']} = {it['qty']*it['unit_cost']}")
                    if st.button(f"❌ حذف", key=f"del_{idx}"):
                        st.session_state.purchase_items.pop(idx)
                        st.rerun()
                    tot += it['qty']*it['unit_cost']
                st.metric("إجمالي الفاتورة", f"{tot:.2f}")
                if st.button("💾 حفظ الفاتورة"):
                    add_purchase(sup, st.session_state.purchase_items)
                    st.session_state.purchase_items = []
                    st.rerun()
        else: st.warning("لا يوجد موردون")

elif menu == "📊 المحاسبة":
    st.markdown("<div class='section-title'>📊 دليل الحسابات والقيود اليومية</div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📒 دليل الحسابات", "📜 القيود اليومية"])
    with tab1:
        accs = get_accounts_tree()
        if accs:
            data = []
            for a in accs:
                bal = get_account_balance(a['id'])
                data.append({"الكود": a['code'], "اسم الحساب": a['name'], "النوع": a['type'], "الرصيد": f"{bal:,.2f}"})
            st.dataframe(pd.DataFrame(data), use_container_width=True)
    with tab2:
        entries = get_all_journal_entries()
        if entries:
            for entry in entries.values():
                with st.expander(f"📌 {entry['date']} - {entry['description']} {entry['reference']}"):
                    st.dataframe(pd.DataFrame(entry['details']), use_container_width=True)
        else: st.info("لا توجد قيود محاسبية بعد")

elif menu == "💰 الضريبة (VAT)":
    st.markdown("<div class='section-title'>💰 إعدادات الضريبة</div>", unsafe_allow_html=True)
    conn = get_conn()
    settings = conn.execute("SELECT default_rate, is_enabled FROM vat_settings WHERE id=1").fetchone()
    conn.close()
    rate = st.number_input("نسبة الضريبة الافتراضية (%)", min_value=0.0, max_value=100.0, value=settings['default_rate']*100, step=0.5) / 100
    enabled = st.checkbox("تفعيل الضريبة", value=bool(settings['is_enabled']))
    if st.button("حفظ الإعدادات"):
        conn = get_conn()
        conn.execute("UPDATE vat_settings SET default_rate=?, is_enabled=?", (rate, 1 if enabled else 0))
        conn.commit()
        conn.close()
        st.success("تم الحفظ")

elif menu == "🏭 الأصول الثابتة":
    st.markdown("<div class='section-title'>🏭 الأصول الثابتة والإهلاك</div>", unsafe_allow_html=True)
    with st.form("add_asset"):
        name = st.text_input("اسم الأصل")
        cost = st.number_input("تكلفة الشراء", min_value=0.0)
        salvage = st.number_input("القيمة الخردة", min_value=0.0)
        life = st.number_input("العمر الإنتاجي (سنوات)", min_value=1, step=1)
        if st.form_submit_button("إضافة أصل"):
            conn = get_conn()
            conn.execute("INSERT INTO fixed_assets (name, purchase_date, purchase_cost, salvage_value, useful_life_years, current_value) VALUES (?,?,?,?,?,?)",
                         (name, date.today().isoformat(), cost, salvage, life, cost))
            conn.commit()
            conn.close()
            st.rerun()
    assets = get_conn().execute("SELECT * FROM fixed_assets").fetchall()
    for a in assets:
        st.write(f"**{a['name']}** - التكلفة: {a['purchase_cost']} - القيمة الحالية: {a['current_value']}")

elif menu == "🏚️ المستودعات":
    st.markdown("<div class='section-title'>🏚️ إدارة المستودعات</div>", unsafe_allow_html=True)
    with st.form("add_wh"):
        name = st.text_input("اسم المستودع")
        loc = st.text_input("الموقع")
        main = st.checkbox("مستودع رئيسي")
        if st.form_submit_button("إضافة"):
            conn = get_conn()
            conn.execute("INSERT INTO warehouses (name, location, is_main) VALUES (?,?,?)", (name, loc, 1 if main else 0))
            conn.commit()
            conn.close()
            st.rerun()
    whs = get_conn().execute("SELECT * FROM warehouses").fetchall()
    for w in whs:
        st.write(f"**{w['name']}** - {w['location']}")

elif menu == "👨‍💼 الموارد البشرية":
    st.markdown("<div class='section-title'>👨‍💼 الموظفون</div>", unsafe_allow_html=True)
    with st.form("add_emp"):
        name = st.text_input("الاسم")
        pos = st.text_input("الوظيفة")
        dept = st.text_input("القسم")
        salary = st.number_input("الراتب", min_value=0.0)
        phone = st.text_input("الجوال")
        email = st.text_input("البريد")
        if st.form_submit_button("إضافة"):
            conn = get_conn()
            conn.execute("INSERT INTO employees (name, position, department, hire_date, salary, phone, email) VALUES (?,?,?,?,?,?,?)",
                         (name, pos, dept, date.today().isoformat(), salary, phone, email))
            conn.commit()
            conn.close()
            st.rerun()
    emps = get_conn().execute("SELECT id, name, position, salary FROM employees").fetchall()
    for e in emps:
        st.write(f"**{e['name']}** - {e['position']} - الراتب: {e['salary']}")

elif menu == "🏭 الإنتاج (BOM)":
    st.markdown("<div class='section-title'>🏭 قوائم المكونات والإنتاج</div>", unsafe_allow_html=True)
    prods = get_all_products()
    prod_names = [p['name'] for p in prods]
    with st.form("add_bom"):
        product = st.selectbox("المنتج النهائي", prod_names)
        comp = st.selectbox("المكون", prod_names)
        qty = st.number_input("الكمية لكل وحدة", min_value=0.1, step=0.1)
        if st.form_submit_button("إضافة إلى BOM"):
            conn = get_conn()
            conn.execute("INSERT INTO bom (product_name, component_name, quantity) VALUES (?,?,?)", (product, comp, qty))
            conn.commit()
            conn.close()
            st.rerun()
    st.subheader("أوامر الإنتاج")
    with st.form("create_prod_order"):
        prod_order = st.selectbox("المنتج", prod_names)
        qty_order = st.number_input("الكمية المطلوبة", min_value=1, step=1)
        if st.form_submit_button("إنشاء أمر إنتاج"):
            order_num = f"PO-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            conn = get_conn()
            conn.execute("INSERT INTO production_orders (order_number, product_name, quantity) VALUES (?,?,?)", (order_num, prod_order, qty_order))
            conn.commit()
            conn.close()
            st.rerun()
    orders = get_conn().execute("SELECT * FROM production_orders ORDER BY created_at DESC").fetchall()
    for o in orders:
        st.write(f"**{o['order_number']}** - {o['product_name']} - {o['quantity']} قطعة - الحالة: {o['status']}")

elif menu == "📈 التقارير المتقدمة":
    advanced_report()

elif menu == "🔄 مرتجعات المبيعات":
    st.markdown("<div class='section-title'>🔄 مرتجعات المبيعات</div>", unsafe_allow_html=True)
    invoices = get_all_sales_invoices()
    if not invoices:
        st.info("لا توجد فواتير بيع مسجلة")
    else:
        invoice_options = {inv['id']: f"{inv['date']} - {inv['customer']} ({len(inv['items'])} منتج)" for inv in invoices}
        selected_inv_id = st.selectbox("اختر فاتورة", list(invoice_options.keys()), format_func=lambda x: invoice_options[x])
        selected_inv = next((inv for inv in invoices if inv['id'] == selected_inv_id), None)
        if selected_inv:
            st.subheader("تفاصيل الفاتورة")
            for item in selected_inv['items']:
                st.write(f"**{item['product']}** - المباع: {item['qty']} - المرتجع: {item.get('returned',0)} - الإجمالي: {item['total']:.2f}")
            product_names = [item['product'] for item in selected_inv['items'] if item['qty'] > item.get('returned',0)]
            if not product_names:
                st.warning("جميع المنتجات تم استردادها بالكامل")
            else:
                selected_product = st.selectbox("المنتج المراد استرداده", product_names)
                item_info = next((it for it in selected_inv['items'] if it['product'] == selected_product), None)
                if item_info:
                    remaining = item_info['qty'] - item_info.get('returned',0)
                    st.write(f"الكمية المتبقية القابلة للاسترداد: {remaining}")
                    return_qty = st.number_input("كمية المرتجع", min_value=1, max_value=remaining, step=1)
                    if st.button("تنفيذ المرتجع"):
                        try:
                            refund = process_return(selected_inv_id, selected_product, return_qty)
                            st.success(f"تم استرداد {return_qty} بنجاح. المبلغ المسترد: {refund:.2f}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"خطأ: {e}")

elif menu == "⚙️ إعدادات النظام":
    st.markdown("<div class='section-title'>⚙️ إعدادات النظام</div>", unsafe_allow_html=True)
    if st.button("📀 إنشاء نسخة احتياطية (SQLite)"):
        backup_file = backup_database()
        with open(backup_file, "rb") as f:
            st.download_button("تحميل النسخة الاحتياطية", f, file_name=backup_file)
        st.success("تم إنشاء النسخة الاحتياطية")
    st.info("يمكنك إدارة المستخدمين يدوياً عبر قاعدة البيانات")

# ========== تذييل الصفحة ==========
st.markdown("---")
st.markdown("<div class='footer'>🎭 نظام ERP المتكامل - المسرحية المحاسبية | تصميم وتطوير سالم التريمي | جميع الحقوق محفوظة © 2025</div>", unsafe_allow_html=True)
