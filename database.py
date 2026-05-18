import psycopg2
import psycopg2.extras
import bcrypt
import streamlit as st
from urllib.parse import urlparse, unquote, quote_plus

def get_connection():
    """إنشاء اتصال بقاعدة بيانات PostgreSQL مع معالجة آمنة للرابط"""
    db_url = st.secrets["DATABASE_URL"]
    
    # تحليل الرابط لاستخراج الأجزاء
    parsed = urlparse(db_url)
    username = parsed.username
    password = unquote(parsed.password) if parsed.password else ""
    host = parsed.hostname
    port = parsed.port or 5432
    database = parsed.path.lstrip("/")
    
    # بناء رابط الاتصال الكامل مع sslmode
    conn_string = f"postgresql://{username}:{quote_plus(password)}@{host}:{port}/{database}?sslmode=require"
    
    conn = psycopg2.connect(conn_string)
    conn.autocommit = False
    return conn

def init_db():
    """إنشاء جميع جداول النظام إذا لم تكن موجودة (PostgreSQL)"""
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            full_name TEXT,
            role TEXT DEFAULT 'staff'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            barcode TEXT UNIQUE,
            category TEXT,
            purchase_price REAL,
            selling_price REAL,
            quantity INTEGER DEFAULT 0,
            reorder_level INTEGER DEFAULT 10
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS stock_movements (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id),
            type TEXT,
            quantity INTEGER,
            date TEXT,
            reference TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id SERIAL PRIMARY KEY,
            type TEXT NOT NULL,
            party_id INTEGER,
            invoice_date TEXT,
            total REAL DEFAULT 0,
            status TEXT DEFAULT 'draft'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS invoice_items (
            id SERIAL PRIMARY KEY,
            invoice_id INTEGER REFERENCES invoices(id),
            product_id INTEGER REFERENCES products(id),
            quantity INTEGER,
            unit_price REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS journal_entries (
            id SERIAL PRIMARY KEY,
            date TEXT,
            description TEXT,
            reference TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS journal_lines (
            id SERIAL PRIMARY KEY,
            entry_id INTEGER REFERENCES journal_entries(id),
            account_name TEXT,
            debit REAL DEFAULT 0,
            credit REAL DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            position TEXT,
            salary REAL,
            join_date TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id SERIAL PRIMARY KEY,
            employee_id INTEGER REFERENCES employees(id),
            date TEXT,
            status TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            parent_id INTEGER REFERENCES accounts(id),
            level INTEGER DEFAULT 1,
            is_debit TEXT DEFAULT 'debit'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS inventory_batches (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id),
            quantity REAL NOT NULL,
            unit_cost REAL NOT NULL,
            batch_date TEXT NOT NULL,
            reference TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS fifo_consumptions (
            id SERIAL PRIMARY KEY,
            batch_id INTEGER REFERENCES inventory_batches(id),
            consumed_qty REAL NOT NULL,
            consumption_date TEXT NOT NULL,
            reference TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS employee_salaries (
            id SERIAL PRIMARY KEY,
            employee_id INTEGER UNIQUE REFERENCES employees(id),
            basic_salary REAL DEFAULT 0,
            housing_allowance REAL DEFAULT 0,
            transport_allowance REAL DEFAULT 0,
            other_allowances REAL DEFAULT 0,
            deductions REAL DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS payroll_runs (
            id SERIAL PRIMARY KEY,
            employee_id INTEGER REFERENCES employees(id),
            month TEXT NOT NULL,
            basic_salary REAL,
            housing_allowance REAL,
            transport_allowance REAL,
            other_allowances REAL,
            total_allowances REAL,
            deductions REAL,
            net_salary REAL,
            journal_entry_id INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS closed_periods (
            id SERIAL PRIMARY KEY,
            period_type TEXT NOT NULL,
            period_value TEXT NOT NULL,
            closed_at TEXT NOT NULL,
            closed_by TEXT NOT NULL,
            UNIQUE(period_type, period_value)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            id SERIAL PRIMARY KEY,
            role_id INTEGER REFERENCES roles(id),
            module TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def create_default_admin():
    """إنشاء مستخدم افتراضي (admin) إذا كانت قاعدة البيانات فارغة"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        hashed = bcrypt.hashpw("admin".encode(), bcrypt.gensalt())
        c.execute(
            "INSERT INTO users (username, password, full_name, role) VALUES (%s, %s, %s, %s)",
            ("admin", hashed.decode(), "مدير النظام", "admin")
        )
        conn.commit()
    conn.close()
