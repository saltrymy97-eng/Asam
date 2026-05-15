import sqlite3
from datetime import datetime

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
            stock INTEGER NOT NULL DEFAULT 0)''')
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
        conn.commit()
    finally:
        conn.close()
    create_default_accounts()

def create_default_accounts():
    defaults = [
        (1, 'الصندوق', 'asset', None),
        (2, 'العملاء', 'asset', None),
        (3, 'المخزون', 'asset', None),
        (4, 'المبيعات', 'revenue', None),
        (5, 'الموردين', 'liability', None),
        (6, 'رأس المال', 'equity', None)
    ]
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

def add_product(name, price, stock):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO products (name, price, stock) VALUES (?,?,?)", (name, price, stock))
        conn.commit()
        record_movement(name, stock, 'in', 'Initial stock')
    finally:
        conn.close()

def get_all_products():
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, price, stock FROM products ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def update_product(product_id, name, price):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET name=?, price=? WHERE id=?", (name, price, product_id))
        if cursor.rowcount == 0:
            raise ValueError(f"Product {product_id} not found")
        conn.commit()
    finally:
        conn.close()

def delete_product(product_id):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM products WHERE id=?", (product_id,))
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Product {product_id} not found")
        pname = row['name']
        cursor.execute("DELETE FROM inventory_movements WHERE product_name=?", (pname,))
        cursor.execute("DELETE FROM sales WHERE product_name=?", (pname,))
        cursor.execute("DELETE FROM purchase_items WHERE product_name=?", (pname,))
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
        elif movement_type == 'out':
            cursor.execute("UPDATE products SET stock = stock - ? WHERE name=?", (qty_change, product_name))
        else:
            raise ValueError("movement_type must be 'in' or 'out'")
        if cursor.rowcount == 0:
            raise ValueError(f"Product '{product_name}' not found")
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

def add_sale(product_name, qty, total):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sales (product_name, qty, total) VALUES (?,?,?)", (product_name, qty, total))
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

def get_customer_balance(customer_id):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT balance FROM customers WHERE id=?", (customer_id,))
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Customer not found")
        return row['balance']
    finally:
        conn.close()

def get_customer_statement(customer_id):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""SELECT id, date, type, amount, reference_id, notes 
            FROM customer_transactions WHERE customer_id=? ORDER BY date DESC, id DESC""", (customer_id,))
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
        elif type_ == 'payment':
            cursor.execute("UPDATE customers SET balance = balance - ? WHERE id=?", (amount, customer_id))
        else:
            raise ValueError("Invalid type")
        conn.commit()
    finally:
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
    if not items:
        raise ValueError("يجب إضافة صنف واحد على الأقل")
    total = sum(item['qty'] * item['unit_cost'] for item in items)
    conn = get_conn()
    try:
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
            cursor.execute("INSERT INTO inventory_movements (product_name, qty, movement_type, notes) VALUES (?,?,'in',?)",
                           (pname, qty, f'شراء فاتورة {purchase_id}'))
        cursor.execute("UPDATE suppliers SET balance = balance + ? WHERE id=?", (total, supplier_id))
        conn.commit()
        post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                   f"فاتورة شراء رقم {purchase_id} من مورد {supplier_id}",
                   'purchase', purchase_id,
                   [{'account_id': 3, 'debit': total, 'credit': 0},
                    {'account_id': 5, 'debit': 0, 'credit': total}])
        return purchase_id
    finally:
        conn.close()

def pay_supplier(supplier_id, amount, notes=""):
    if amount <= 0:
        raise ValueError("Amount must be positive")
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, balance FROM suppliers WHERE id=?", (supplier_id,))
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Supplier not found")
        if amount > row['balance']:
            raise ValueError("المبلغ أكبر من الرصيد")
        cursor.execute("UPDATE suppliers SET balance = balance - ? WHERE id=?", (amount, supplier_id))
        conn.commit()
    finally:
        conn.close()
    post_entry(datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
               f"دفع للمورد {supplier_id} - {notes}",
               'supplier_payment', supplier_id,
               [{'account_id': 5, 'debit': amount, 'credit': 0},
                {'account_id': 1, 'debit': 0, 'credit': amount}])

def add_sale_with_customer(product_name, qty, total, customer_id=None):
    sale_id = add_sale(product_name, qty, total)
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

def create_account(code, name, type, parent_id=None):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO accounts (code, name, type, parent_id) VALUES (?,?,?,?)",
                       (code, name, type, parent_id))
        conn.commit()
        return cursor.lastrowid
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
        cursor.execute("SELECT COALESCE(SUM(debit),0) as d, COALESCE(SUM(credit),0) as c FROM journal_details WHERE account_id=?",
                       (account_id,))
        sums = cursor.fetchone()
        debit, credit = sums['d'], sums['c']
        if acc_type in ('asset', 'expense'):
            return debit - credit
        else:
            return credit - debit
    finally:
        conn.close()

def post_entry(date, description, reference_type=None, reference_id=None, details=None):
    if not details:
        raise ValueError("تفاصيل مطلوبة")
    total_debit = sum(d['debit'] for d in details)
    total_credit = sum(d['credit'] for d in details)
    if abs(total_debit - total_credit) > 0.001:
        raise ValueError("القيد غير متوازن")
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO journal_entries (date, description, reference_type, reference_id) VALUES (?,?,?,?)",
                       (date, description, reference_type, reference_id))
        entry_id = cursor.lastrowid
        for detail in details:
            cursor.execute("INSERT INTO journal_details (entry_id, account_id, debit, credit) VALUES (?,?,?,?)",
                           (entry_id, detail['account_id'], detail['debit'], detail['credit']))
        conn.commit()
        return entry_id
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
            ORDER BY je.date DESC, je.id DESC""")
        rows = cursor.fetchall()
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
    finally:
        conn.close()
import streamlit as st
from database import init_db, add_product, get_all_products, update_product, delete_product, update_stock, get_low_stock

init_db()

if 'editing_product' not in st.session_state:
    st.session_state.editing_product = None
if 'stock_product' not in st.session_state:
    st.session_state.stock_product = None
if 'confirm_delete' not in st.session_state:
    st.session_state.confirm_delete = None

st.set_page_config(page_title="إدارة المنتجات", layout="wide")
st.title("📦 إدارة المنتجات")

products = get_all_products()
low_stock_items = get_low_stock(5)
col1, col2 = st.columns(2)
col1.metric("إجمالي المنتجات", len(products))
col2.metric("منخفضة المخزون (≤5)", len(low_stock_items), delta_color="inverse")
st.markdown("---")

with st.expander("➕ إضافة منتج جديد", expanded=False):
    with st.form("add_product_form", clear_on_submit=True):
        name = st.text_input("اسم المنتج")
        price = st.number_input("السعر", min_value=0.0, step=0.01)
        stock = st.number_input("المخزون الأولي", min_value=0, step=1)
        if st.form_submit_button("إضافة"):
            if not name.strip():
                st.error("الاسم مطلوب")
            else:
                try:
                    add_product(name.strip(), price, stock)
                    st.success(f"تم إضافة {name}")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

if products:
    st.subheader("قائمة المنتجات")
def add_sale_with_customer(product_name, qty, total, customer_id=None):
    conn = get_conn()
    try:
        cursor = conn.cursor()
        
        # 1. سجل البيع
        cursor.execute("INSERT INTO sales (product_name, qty, total) VALUES (?,?,?)", 
                      (product_name, qty, total))
        sale_id = cursor.lastrowid
        
        # 2. حدث المخزون
        cursor.execute("UPDATE products SET stock = stock - ? WHERE name=?", 
                      (qty, product_name))
        
        # 3. سجل حركة المخزون
        cursor.execute("INSERT INTO inventory_movements (product_name, qty, movement_type, notes) VALUES (?,?,'out',?)",
                      (product_name, qty, f'بيع فاتورة {sale_id}'))
        
        # 4. إذا كان هناك عميل، سجل المعاملة
        if customer_id:
            cursor.execute("INSERT INTO customer_transactions (customer_id, type, amount, reference_id, notes) VALUES (?,?,?,?,?)",
                         (customer_id, 'sale', total, sale_id, f'فاتورة بيع {product_name}'))
            cursor.execute("UPDATE customers SET balance = balance + ? WHERE id=?", 
                         (total, customer_id))
            debit_account = 2  # العملاء
        else:
            debit_account = 1  # الصندوق
        
        # 5. سجل القيد المحاسبي (في نفس الـ transaction)
        cursor.execute("INSERT INTO journal_entries (date, description, reference_type, reference_id) VALUES (datetime('now','localtime'),?,?,?)",
                     (f"بيع - فاتورة {sale_id}", 'sale', sale_id))
        entry_id = cursor.lastrowid
        
        cursor.execute("INSERT INTO journal_details (entry_id, account_id, debit, credit) VALUES (?,?,?,?)",
                     (entry_id, debit_account, total, 0))
        cursor.execute("INSERT INTO journal_details (entry_id, account_id, debit, credit) VALUES (?,?,?,?)",
                     (entry_id, 4, 0, total))  # المبيعات
        
        # 6. التزم الكل معاً
        conn.commit()
        return sale_id
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
import streamlit as st
from database import get_all_products, get_all_customers, update_stock, add_sale_with_customer, get_low_stock

st.set_page_config(page_title="الكاشير", layout="wide")
st.title("🛒 واجهة البيع")

if 'cart' not in st.session_state:
    st.session_state.cart = []

products = {p['name']: p for p in get_all_products()}
customers = get_all_customers()
customer_options = {c['id']: c['name'] for c in customers}
customer_options[None] = "بدون عميل (بيع نقدي)"

# اختيار العميل
selected_customer_id = st.selectbox(
    "👤 اختر العميل",
    options=list(customer_options.keys()),
    format_func=lambda x: customer_options[x]
)

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("➕ إضافة منتج للسلة")
    product_names = list(products.keys())
    selected_product = st.selectbox("المنتج", product_names)
    qty = st.number_input("الكمية", min_value=1, step=1, value=1)
    if st.button("إضافة إلى السلة"):
        product = products[selected_product]
        if product['stock'] >= qty:
            st.session_state.cart.append({
                "name": selected_product,
                "price": product['price'],
                "qty": qty,
                "total": product['price'] * qty
            })
            st.success(f"تمت إضافة {qty} × {selected_product}")
            st.rerun()
        else:
            st.error(f"المخزون غير كافٍ (متوفر: {product['stock']})")

with col2:
    st.subheader("🧾 السلة")
    if st.session_state.cart:
        cart_df = []
        total = 0
        for idx, item in enumerate(st.session_state.cart):
            st.write(f"{item['name']} - {item['qty']} × {item['price']} = {item['total']}")
            total += item['total']
            if st.button(f"❌ حذف", key=f"del_{idx}"):
                st.session_state.cart.pop(idx)
                st.rerun()
        st.metric("الإجمالي", f"{total:.2f}")
        if st.button("✅ إتمام البيع"):
            try:
                for item in st.session_state.cart:
                    # تحديث المخزون
                    update_stock(item['name'], item['qty'], 'out', f"بيع - عميل {selected_customer_id}")
                    # تسجيل البيع مع العميل والقيد المحاسبي
                    add_sale_with_customer(item['name'], item['qty'], item['total'], selected_customer_id)
                st.session_state.cart = []
                st.success("تمت عملية البيع بنجاح!")
                st.rerun()
            except Exception as e:
                st.error(f"خطأ: {e}")
    else:
        st.info("السلة فارغة")

# تنبيهات المخزون المنخفض
low = get_low_stock(5)
if low:
    st.sidebar.warning("⚠️ منتجات منخفضة المخزون:")
    for p in low:
        st.sidebar.write(f"{p['name']}: {p['stock']} قطعة")
import streamlit as st
from database import get_all_customers, add_customer, get_customer_statement, receive_payment, get_customer_balance

st.set_page_config(page_title="العملاء", layout="wide")
st.title("👥 إدارة العملاء والديون")

tab1, tab2, tab3 = st.tabs(["➕ إضافة عميل", "📋 قائمة العملاء", "💰 تحصيل دفعة"])

with tab1:
    with st.form("add_customer"):
        name = st.text_input("الاسم")
        phone = st.text_input("الجوال")
        address = st.text_input("العنوان")
        if st.form_submit_button("إضافة"):
            if name.strip():
                add_customer(name, phone, address)
                st.success(f"تم إضافة {name}")
                st.rerun()
            else:
                st.error("الاسم مطلوب")

with tab2:
    customers = get_all_customers()
    if customers:
        for c in customers:
            with st.expander(f"{c['name']} - الرصيد: {c['balance']:.2f}"):
                st.write(f"📞 {c['phone']} | 🏠 {c['address']}")
                if st.button(f"كشف حساب", key=f"stmt_{c['id']}"):
                    st.subheader(f"كشف حساب {c['name']}")
                    stmt = get_customer_statement(c['id'])
                    if stmt:
                        st.dataframe(stmt)
                    else:
                        st.info("لا توجد معاملات")
    else:
        st.info("لا يوجد عملاء")

with tab3:
    customers = get_all_customers()
    if customers:
        customer_map = {c['id']: f"{c['name']} (الرصيد: {c['balance']:.2f})" for c in customers}
        selected_id = st.selectbox("اختر العميل", options=list(customer_map.keys()), format_func=lambda x: customer_map[x])
        amount = st.number_input("المبلغ", min_value=0.01, step=100.0)
        notes = st.text_input("ملاحظات")
        if st.button("تسجيل دفعة"):
            try:
                receive_payment(selected_id, amount, notes)
                st.success(f"تم استلام {amount} من العميل")
                st.rerun()
            except Exception as e:
                st.error(str(e))
    else:
        st.warning("لا يوجد عملاء لإضافة دفعة")
import streamlit as st
from database import get_all_suppliers, add_supplier, add_purchase, get_all_products

st.set_page_config(page_title="الموردين والمشتريات", layout="wide")
st.title("📦 إدارة الموردين والمشتريات")

tab1, tab2, tab3 = st.tabs(["➕ إضافة مورد", "📋 قائمة الموردين", "🛒 فاتورة شراء"])

with tab1:
    with st.form("add_supplier"):
        name = st.text_input("اسم المورد")
        phone = st.text_input("الجوال")
        if st.form_submit_button("إضافة"):
            if name.strip():
                add_supplier(name, phone)
                st.success(f"تم إضافة {name}")
                st.rerun()
            else:
                st.error("الاسم مطلوب")

with tab2:
    suppliers = get_all_suppliers()
    if suppliers:
        for s in suppliers:
            st.write(f"**{s['name']}** - 📞 {s['phone']} - الرصيد: {s['balance']:.2f}")
    else:
        st.info("لا يوجد موردون")

with tab3:
    suppliers = get_all_suppliers()
    if suppliers:
        supplier_map = {s['id']: s['name'] for s in suppliers}
        selected_supplier = st.selectbox("المورد", options=list(supplier_map.keys()), format_func=lambda x: supplier_map[x])
        
        # إضافة أصناف المشتريات
        if 'purchase_items' not in st.session_state:
            st.session_state.purchase_items = []
        
        products = get_all_products()
        product_names = [p['name'] for p in products]
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            pname = st.selectbox("المنتج", product_names, key="pname")
        with col2:
            qty = st.number_input("الكمية", min_value=1, step=1, key="qty")
        with col3:
            cost = st.number_input("سعر الشراء", min_value=0.01, step=0.01, key="cost")
        with col4:
            if st.button("➕ إضافة صنف"):
                st.session_state.purchase_items.append({"product_name": pname, "qty": qty, "unit_cost": cost})
                st.success("تمت الإضافة")
        
        if st.session_state.purchase_items:
            st.subheader("أصناف الفاتورة")
            total = 0
            for idx, item in enumerate(st.session_state.purchase_items):
                st.write(f"{item['product_name']} - {item['qty']} × {item['unit_cost']} = {item['qty']*item['unit_cost']}")
                if st.button(f"حذف", key=f"del_{idx}"):
                    st.session_state.purchase_items.pop(idx)
                    st.rerun()
                total += item['qty'] * item['unit_cost']
            st.metric("إجمالي الفاتورة", f"{total:.2f}")
            if st.button("حفظ الفاتورة"):
                try:
                    add_purchase(selected_supplier, st.session_state.purchase_items)
                    st.session_state.purchase_items = []
                    st.success("تم تسجيل فاتورة الشراء وتحديث المخزون")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    else:
        st.warning("يجب إضافة مورد أولاً")
import streamlit as st
import pandas as pd
from database import get_accounts_tree, get_all_journal_entries, create_account, get_account_balance

st.set_page_config(page_title="المحاسبة", layout="wide")
st.title("📊 دليل الحسابات والقيود")

tab1, tab2 = st.tabs(["📒 دليل الحسابات", "📜 القيود اليومية"])

with tab1:
    accounts = get_accounts_tree()
    if accounts:
        # عرض شجري بسيط
        df = pd.DataFrame(accounts)
        df['الرصيد'] = df['id'].apply(get_account_balance)
        st.dataframe(df[['code', 'name', 'type', 'الرصيد']])
        
        with st.expander("➕ إضافة حساب جديد"):
            code = st.text_input("كود الحساب")
            name = st.text_input("الاسم")
            acc_type = st.selectbox("النوع", ['asset','liability','equity','revenue','expense'])
            parent_id = st.number_input("معرف الحساب الأب (اختياري)", min_value=0, value=0, step=1)
            if st.button("إنشاء"):
                if code and name:
                    create_account(code, name, acc_type, parent_id if parent_id>0 else None)
                    st.success("تم إضافة الحساب")
                    st.rerun()
                else:
                    st.error("الكود والاسم مطلوبان")
    else:
        st.info("لا توجد حسابات")

with tab2:
    entries = get_all_journal_entries()
    if entries:
        for entry in entries:
            with st.expander(f"{entry['date']} - {entry['description']}"):
                st.write(f"مرجع: {entry['reference_type']} - {entry['reference_id']}")
                details_df = pd.DataFrame(entry['details'])
                st.dataframe(details_df[['account_name', 'debit', 'credit']])
    else:
        st.info("لا توجد قيود محاسبية بعد")
import streamlit as st
import pandas as pd
from database import get_accounts_tree, get_account_balance, get_sales_summary, get_all_journal_entries

st.set_page_config(page_title="التقارير المالية", layout="wide")
st.title("📈 التقارير المالية")

# قائمة الدخل
st.subheader("📊 قائمة الدخل")
revenue_accounts = []
expense_accounts = []
for acc in get_accounts_tree():
    bal = get_account_balance(acc['id'])
    if acc['type'] == 'revenue':
        revenue_accounts.append({"الحساب": acc['name'], "الرصيد": bal})
    elif acc['type'] == 'expense':
        expense_accounts.append({"الحساب": acc['name'], "الرصيد": bal})

total_revenue = sum(r['الرصيد'] for r in revenue_accounts)
total_expense = sum(e['الرصيد'] for e in expense_accounts)

col1, col2 = st.columns(2)
with col1:
    st.write("**الإيرادات**")
    if revenue_accounts:
        st.dataframe(pd.DataFrame(revenue_accounts))
    st.metric("إجمالي الإيرادات", f"{total_revenue:.2f}")
with col2:
    st.write("**المصروفات**")
    if expense_accounts:
        st.dataframe(pd.DataFrame(expense_accounts))
    st.metric("إجمالي المصروفات", f"{total_expense:.2f}")

net = total_revenue - total_expense
st.metric("صافي الربح / الخسارة", f"{net:.2f}", delta_color="normal" if net>=0 else "inverse")

# الميزانية العمومية (مبسطة)
st.subheader("📋 الميزانية العمومية")
assets = []
liabilities = []
equity = []
for acc in get_accounts_tree():
    bal = get_account_balance(acc['id'])
    if acc['type'] == 'asset':
        assets.append({"الحساب": acc['name'], "الرصيد": bal})
    elif acc['type'] == 'liability':
        liabilities.append({"الحساب": acc['name'], "الرصيد": bal})
    elif acc['type'] == 'equity':
        equity.append({"الحساب": acc['name'], "الرصيد": bal})

col1, col2, col3 = st.columns(3)
with col1:
    st.write("**الأصول**")
    st.dataframe(pd.DataFrame(assets))
    st.metric("إجمالي الأصول", f"{sum(a['الرصيد'] for a in assets):.2f}")
with col2:
    st.write("**الخصوم**")
    st.dataframe(pd.DataFrame(liabilities))
    st.metric("إجمالي الخصوم", f"{sum(l['الرصيد'] for l in liabilities):.2f}")
with col3:
    st.write("**حقوق الملكية**")
    st.dataframe(pd.DataFrame(equity))
    st.metric("إجمالي حقوق الملكية", f"{sum(e['الرصيد'] for e in equity):.2f}")

# ملخص المبيعات
sales_sum = get_sales_summary()
st.subheader("🛍️ ملخص المبيعات")
st.metric("عدد الفواتير", sales_sum['total_sales'])
st.metric("إجمالي الإيرادات", f"{sales_sum['total_revenue']:.2f}")
import streamlit as st
import sys
import os

# إضافة المجلد الحالي إلى مسار Python (للتأكد)
sys.path.append(os.path.dirname(__file__))

st.set_page_config(page_title="نظام ERP", layout="wide", initial_sidebar_state="expanded")

# تطبيق CSS بسيط (يمكنك إضافة CSS النظام الأصلي هنا)
st.markdown("""
<style>
    .stButton button { background-color: #6f42c1; color: white; border-radius: 20px; }
    .css-1d391kg { background-color: #1e1a2e; }
</style>
""", unsafe_allow_html=True)

st.title("🏢 نظام ERP المتكامل")
st.caption("إدارة المبيعات، العملاء، الموردين، والمحاسبة")

# قائمة الصفحات (إضافة كل الوحدات)
pages = {
    "🏠 لوحة التحكم": "dashboard_ui.py",  # لم ننشئها بعد، يمكن إضافتها لاحقاً
    "📦 المنتجات": "products_ui.py",
    "🛒 الكاشير": "sales_ui.py",
    "👥 العملاء": "customers_ui.py",
    "📦 الموردين والمشتريات": "suppliers_ui.py",
    "📊 المحاسبة": "accounting_ui.py",
    "📈 التقارير": "reports_ui.py"
}

# الشريط الجانبي
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/theater-mask.png", width=80)
    st.markdown("## 🎭 المسرحية المحاسبية")
    choice = st.radio("اختر الوحدة", list(pages.keys()))

# عرض الصفحة المختارة
try:
    page_file = pages[choice]
    # استخدام exec لتحميل الملف كوحدة منفصلة (أو يمكن استدعاء main() لكل ملف)
    # الطريقة المبسطة: نستخدم __import__ لكن الأسهل هو تشغيل الملف مباشرة بطريقة streamlit.
    # بدلاً من ذلك، سنستخدم st.switch_page إن أمكن أو نعرض محتوى الملف ديناميكياً.
    # لكن بما أن كل ملف له واجهته المستقلة، يمكننا توجيه المستخدم لتشغيل كل ملف على حدة.
    # الحل الأمثل: ننشئ صفحة مؤقتة تعيد توجيه إلى الملف المناسب.
    st.info(f"لتشغيل واجهة {choice}، استخدم الأمر: streamlit run {page_file}")
    st.code(f"streamlit run {page_file}", language="bash")
except Exception as e:
    st.error(f"خطأ: {e}")
import streamlit as st
from database import init_db, add_product, get_all_products, update_product, delete_product, update_stock, get_low_stock

init_db()

if 'editing_product' not in st.session_state:
    st.session_state.editing_product = None
if 'stock_product' not in st.session_state:
    st.session_state.stock_product = None
if 'confirm_delete' not in st.session_state:
    st.session_state.confirm_delete = None

st.set_page_config(page_title="إدارة المنتجات", layout="wide")
st.title("📦 إدارة المنتجات")

products = get_all_products()
low_stock_items = get_low_stock(5)
col1, col2 = st.columns(2)
col1.metric("إجمالي المنتجات", len(products))
col2.metric("منخفضة المخزون (≤5)", len(low_stock_items))
st.markdown("---")

with st.expander("➕ إضافة منتج جديد", expanded=False):
    with st.form("add_product_form", clear_on_submit=True):
        name = st.text_input("اسم المنتج")
        price = st.number_input("السعر", min_value=0.0, step=0.01)
        stock = st.number_input("المخزون الأولي", min_value=0, step=1)
        if st.form_submit_button("إضافة"):
            if not name.strip():
                st.error("الاسم مطلوب")
            else:
                try:
                    add_product(name.strip(), price, stock)
                    st.success(f"تم إضافة {name}")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

if products:
    st.subheader("قائمة المنتجات")
    for p in products:
        col1, col2, col3, col4, col5 = st.columns([2,1,1,1,1])
        col1.write(f"**{p['name']}**")
        col2.write(f"{p['price']:.2f}")
        col3.write(f"{p['stock']}")
        if col4.button("تعديل المخزون", key=f"stock_{p['id']}"):
            st.session_state.stock_product = p
        if col5.button("حذف", key=f"del_{p['id']}"):
            st.session_state.confirm_delete = p
        st.markdown("---")

if st.session_state.stock_product:
    p = st.session_state.stock_product
    with st.form("stock_form"):
        st.write(f"تعديل مخزون {p['name']}")
        change = st.number_input("التغيير (موجب للإضافة، سالب للسحب)", step=1, value=0)
        notes = st.text_input("سبب الحركة")
        if st.form_submit_button("تطبيق"):
            try:
                update_stock(p['name'], abs(change), 'in' if change>0 else 'out', notes)
                st.success("تم تحديث المخزون")
                st.session_state.stock_product = None
                st.rerun()
            except Exception as e:
                st.error(str(e))

if st.session_state.confirm_delete:
    p = st.session_state.confirm_delete
    st.warning(f"هل أنت متأكد من حذف {p['name']}؟")
    col1, col2 = st.columns(2)
    if col1.button("نعم"):
        delete_product(p['id'])
        st.session_state.confirm_delete = None
        st.rerun()
    if col2.button("لا"):
        st.session_state.confirm_delete = None
        st.rerun()

