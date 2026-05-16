import sqlite3
from datetime import datetime, date
import streamlit as st
import pandas as pd
import plotly.express as px

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
    
    html, body, [class*="css"] {
        font-family: 'Cairo', sans-serif;
    }
    
    .main {
        background: linear-gradient(135deg, #f8f9fc 0%, #f0f2f6 100%);
    }
    
    h1, h2, h3, .stMarkdown h1, .stMarkdown h2 {
        color: #1a1a2e;
        font-weight: 700;
    }
    
    /* البطاقات */
    .metric-card {
        background: white;
        border-radius: 28px;
        padding: 22px 15px;
        box-shadow: 0 8px 25px rgba(0,0,0,0.05);
        text-align: center;
        transition: all 0.3s ease;
        border: 1px solid rgba(106, 13, 173, 0.1);
    }
    .metric-card:hover {
        transform: translateY(-6px);
        box-shadow: 0 20px 35px rgba(106, 13, 173, 0.15);
        border-color: #6a0dad;
    }
    .metric-card h3 {
        font-size: 2.2rem;
        margin: 12px 0;
        background: linear-gradient(135deg, #6a0dad, #8b5cf6);
        background-clip: text;
        -webkit-background-clip: text;
        color: transparent;
    }
    .metric-card p {
        color: #4a5568;
        font-weight: 600;
        margin: 0;
        font-size: 1rem;
    }
    
    /* الأزرار */
    .stButton > button {
        background: linear-gradient(135deg, #6a0dad, #8b5cf6);
        color: white;
        border-radius: 40px;
        border: none;
        padding: 10px 25px;
        font-weight: 600;
        transition: all 0.3s ease;
        width: 100%;
        font-size: 0.9rem;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(106, 13, 173, 0.3);
        background: linear-gradient(135deg, #5a0c9e, #7c3aed);
    }
    
    /* الشريط الجانبي */
    .css-1d391kg {
        background: linear-gradient(180deg, #0f0f1f, #1a1a2e);
        border-radius: 0 35px 35px 0;
    }
    .css-1d391kg .stMarkdown, .css-1d391kg .stSelectbox label {
        color: #f0f0f0;
    }
    .css-1d391kg .stSelectbox > div > div {
        background-color: rgba(255,255,255,0.1);
        border-radius: 30px;
        color: white;
    }
    
    /* الجداول */
    .dataframe {
        border-radius: 20px;
        overflow: hidden;
        box-shadow: 0 8px 20px rgba(0,0,0,0.05);
        border: none;
    }
    .dataframe th {
        background: linear-gradient(135deg, #6a0dad, #8b5cf6);
        color: white;
        font-weight: 600;
        padding: 12px;
    }
    .dataframe td {
        padding: 10px;
        border-bottom: 1px solid #e2e8f0;
    }
    
    /* التبويبات */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
        background: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        background: white;
        border-radius: 40px;
        padding: 8px 24px;
        font-weight: 600;
        color: #4a5568;
        border: 1px solid #e2e8f0;
        transition: 0.2s;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #6a0dad, #8b5cf6);
        color: white;
        border: none;
        box-shadow: 0 4px 12px rgba(106,13,173,0.2);
    }
    
    /* العناوين */
    .section-title {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 30px;
        border-right: 6px solid #6a0dad;
        padding-right: 20px;
        color: #1a1a2e;
        display: inline-block;
    }
    
    /* الكاردات الداخلية */
    .info-card {
        background: white;
        border-radius: 25px;
        padding: 18px;
        margin: 10px 0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03);
        border: 1px solid #e9edf2;
    }
    
    .footer {
        text-align: center;
        margin-top: 55px;
        padding: 22px;
        background: white;
        border-radius: 50px;
        color: #4a5568;
        font-size: 0.85rem;
        box-shadow: 0 -3px 15px rgba(0,0,0,0.02);
    }
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
    """تحديث قاعدة البيانات بإضافة الأعمدة الجديدة إذا لم تكن موجودة"""
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN vat_rate REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN vat_amount REAL DEFAULT 0")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE sales ADD COLUMN vat_rate REAL DEFAULT 0")
    except:
        pass
    conn.commit()
    conn.close()

def init_db():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        # الجداول الأساسية
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
        cursor.execute("INSERT OR IGNORE INTO vat_settings (id, default_rate, is_enabled) VALUES (1, 0.15, 1)")
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
        cursor.execute('''CREATE TABLE IF NOT EXISTS warehouse_stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            UNIQUE(warehouse_id, product_name))''')
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
        conn.commit()
    finally:
        conn.close()
    create_default_accounts()
    upgrade_database()

def create_default_accounts():
    defaults = [(1, 'الصندوق', 'asset'), (2, 'العملاء', 'asset'),
                (3, 'المخزون', 'asset'), (4, 'المبيعات', 'revenue'),
                (5, 'الموردين', 'liability'), (6, 'رأس المال', 'equity')]
    conn = get_conn()
    try:
        cursor = conn.cursor()
        for code, name, type_ in defaults:
            cursor.execute("INSERT OR IGNORE INTO accounts (id, code, name, type) VALUES (?,?,?,?)", (code, code, name, type_))
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
        try:
            cursor.execute("SELECT id, name, price, stock, vat_rate FROM products ORDER BY name")
        except sqlite3.OperationalError:
            cursor.execute("SELECT id, name, price, stock FROM products ORDER BY name")
            rows = cursor.fetchall()
            return [dict(row, vat_rate=0.0) for row in rows]
        else:
            return [dict(row) for row in cursor.fetchall()]
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
        cursor.execute("INSERT INTO inventory_movements (product_name, qty, movement_type, notes) VALUES (?,?,?,?)", (product_name, qty, movement_type, notes))
        conn.commit()
    finally:
        conn.close()

def add_sale(product_name, qty, total, vat_amount=0, vat_rate=0):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sales (product_name, qty, total, vat_amount, vat_rate) VALUES (?,?,?,?,?)", (product_name, qty, total, vat_amount, vat_rate))
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
        cursor.execute("SELECT date, type, amount, notes FROM customer_transactions WHERE customer_id=? ORDER BY date DESC", (customer_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def add_customer_transaction(customer_id, type_, amount, reference_id=None, notes=""):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO customer_transactions (customer_id, type, amount, reference_id, notes) VALUES (?,?,?,?,?)", (customer_id, type_, amount, reference_id, notes))
        if type_ == 'sale':
            cursor.execute("UPDATE customers SET balance = balance + ? WHERE id=?", (amount, customer_id))
        else:
            cursor.execute("UPDATE customers SET balance = balance - ? WHERE id=?", (amount, customer_id))
        conn.commit()
    finally:
        conn.close()

def receive_payment(customer_id, amount, notes=""):
    add_customer_transaction(customer_id, 'payment', amount, None, notes)
    post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), f"تحصيل دفعة من عميل", 'payment', customer_id,
               [{'account_id': 1, 'debit': amount, 'credit': 0}, {'account_id': 2, 'debit': 0, 'credit': amount}])

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
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO journal_entries (date, description, reference_type, reference_id) VALUES (?,?,?,?)", (date, description, ref_type, ref_id))
        entry_id = cursor.lastrowid
        for d in details:
            cursor.execute("INSERT INTO journal_details (entry_id, account_id, debit, credit) VALUES (?,?,?,?)", (entry_id, d['account_id'], d['debit'], d['credit']))
        conn.commit()
    finally:
        conn.close()

def get_account_balance(account_id):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(debit),0) - COALESCE(SUM(credit),0) FROM journal_details WHERE account_id=?", (account_id,))
        return cursor.fetchone()[0]
    finally:
        conn.close()

def get_accounts_tree():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, code, name, type FROM accounts ORDER BY code")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

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
    
    # تجميع القيود لعرضها بشكل أفضل
    entries = {}
    for row in rows:
        eid = row['id']
        if eid not in entries:
            entries[eid] = {
                'date': row['date'],
                'description': row['description'],
                'reference': f"{row['reference_type']} - {row['reference_id']}" if row['reference_id'] else '',
                'details': []
            }
        entries[eid]['details'].append({
            'account': row['account_name'],
            'debit': row['debit'],
            'credit': row['credit']
        })
    return entries

def advanced_report():
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

# ============================================================
#                         واجهة المستخدم
# ============================================================

st.sidebar.markdown("<h2 style='text-align:center; color:white; margin-top:10px;'>🎭 المسرحية المحاسبية</h2>", unsafe_allow_html=True)
st.sidebar.markdown("---")

menu = st.sidebar.radio("القائمة الرئيسية",
    ["🏠 لوحة التحكم", "📦 المنتجات", "🛒 الكاشير", "👥 العملاء", "📦 الموردين",
     "📊 المحاسبة", "💰 الضريبة (VAT)", "🏭 الأصول الثابتة", "🏚️ المستودعات",
     "👨‍💼 الموارد البشرية", "🏭 الإنتاج (BOM)", "📈 التقارير المتقدمة"])

st.sidebar.markdown("---")
st.sidebar.caption("© 2025 - جميع الحقوق محفوظة")

# ---------- لوحة التحكم ----------
if menu == "🏠 لوحة التحكم":
    st.markdown("<div class='section-title'>🏠 لوحة القيادة</div>", unsafe_allow_html=True)
    products = get_all_products()
    sales_sum = get_sales_summary()
    low_stock = get_low_stock(5)
    customers = get_all_customers()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"<div class='metric-card'><p>📦 إجمالي المنتجات</p><h3>{len(products)}</h3></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='metric-card'><p>💰 إجمالي المبيعات</p><h3>{sales_sum['total_revenue']:,.0f}</h3></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='metric-card'><p>⚠️ مخزون منخفض</p><h3>{len(low_stock)}</h3></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='metric-card'><p>👥 العملاء</p><h3>{len(customers)}</h3></div>", unsafe_allow_html=True)
    
    st.markdown("---")
    if low_stock:
        st.warning("⚠️ المنتجات منخفضة المخزون (≤5): " + ", ".join([p['name'] for p in low_stock]))
    else:
        st.success("✅ جميع المنتجات بمخزون جيد")

# ---------- المنتجات ----------
elif menu == "📦 المنتجات":
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
        df['السعر'] = df['price'].apply(lambda x: f"{x:,.2f}")
        df['الضريبة'] = df['vat_rate'].apply(lambda x: f"{x*100:.0f}%")
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

# ---------- الكاشير ----------
elif menu == "🛒 الكاشير":
    st.markdown("<div class='section-title'>🛒 واجهة البيع</div>", unsafe_allow_html=True)
    if 'cart' not in st.session_state:
        st.session_state.cart = []
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
            else:
                st.error("المخزون غير كافٍ")
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
                for item in st.session_state.cart:
                    sub = item['price'] * item['qty']
                    vat_amt = sub * item['vat']
                    add_sale_with_customer(item['name'], item['qty'], sub+vat_amt, vat_amt, item['vat'], selected_cust if selected_cust!=None else None)
                st.session_state.cart = []
                st.success("تم البيع بنجاح")
                st.rerun()
        else:
            st.info("السلة فارغة")

# ---------- العملاء ----------
elif menu == "👥 العملاء":
    st.markdown("<div class='section-title'>👥 العملاء والديون</div>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["📋 قائمة العملاء", "➕ إضافة عميل"])
    with tab1:
        for c in get_all_customers():
            with st.expander(f"{c['name']} - الرصيد: {c['balance']:.2f}"):
                st.write(f"📞 {c['phone']} | 🏠 {c['address']}")
                if st.button(f"📜 كشف حساب", key=f"stmt_{c['id']}"):
                    stmt = get_customer_statement(c['id'])
                    st.dataframe(stmt)
    with tab2:
        with st.form("add_cust"):
            name = st.text_input("الاسم")
            phone = st.text_input("الجوال")
            address = st.text_input("العنوان")
            if st.form_submit_button("إضافة"):
                add_customer(name, phone, address)
                st.rerun()

# ---------- الموردين ----------
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
            if 'purchase_items' not in st.session_state:
                st.session_state.purchase_items = []
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
        else:
            st.warning("لا يوجد موردون")

# ---------- المحاسبة (محسّنة) ----------
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
        else:
            st.info("لا توجد حسابات")
    with tab2:
        entries = get_all_journal_entries()
        if entries:
            for entry_id, entry in entries.items():
                with st.expander(f"📌 {entry['date']} - {entry['description']} {entry['reference']}"):
                    details_df = pd.DataFrame(entry['details'])
                    details_df['debit'] = details_df['debit'].apply(lambda x: f"{x:,.2f}" if x>0 else "")
                    details_df['credit'] = details_df['credit'].apply(lambda x: f"{x:,.2f}" if x>0 else "")
                    st.dataframe(details_df, use_container_width=True)
        else:
            st.info("✨ لا توجد قيود محاسبية مسجلة حتى الآن. قم بإجراء عمليات بيع أو شراء لتظهر هنا.")

# ---------- الضريبة ----------
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

# ---------- الأصول الثابتة ----------
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

# ---------- المستودعات ----------
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

# ---------- الموارد البشرية ----------
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

# ---------- الإنتاج ----------
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

# ---------- التقارير المتقدمة ----------
elif menu == "📈 التقارير المتقدمة":
    st.markdown("<div class='section-title'>📈 التحليلات والتقارير المتقدمة</div>", unsafe_allow_html=True)
    advanced_report()

# ============================================================
#                         تذييل الصفحة
# ============================================================
st.markdown("---")
st.markdown("<div class='footer'>🎭 نظام ERP المتكامل - المسرحية المحاسبية | تصميم وتطوير سالم التريمي | جميع الحقوق محفوظة © 2025</div>", unsafe_allow_html=True)
