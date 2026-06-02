# database.py - قاعدة بيانات نظام ERP كاملة (SQLite) مع VAT ومراكز التكلفة والعملات والبنوك والمرفقات
import sqlite3
import bcrypt

DB_PATH = "erp.db"

def get_connection():
    """إنشاء اتصال بقاعدة البيانات"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """إنشاء جميع جداول النظام إذا لم تكن موجودة"""
    conn = get_connection()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        full_name TEXT,
        role TEXT DEFAULT 'staff'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        barcode TEXT UNIQUE,
        category TEXT,
        purchase_price REAL,
        selling_price REAL,
        quantity INTEGER DEFAULT 0,
        reorder_level INTEGER DEFAULT 10
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS stock_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        type TEXT,
        quantity INTEGER,
        date TEXT,
        reference TEXT,
        FOREIGN KEY (product_id) REFERENCES products(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        address TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        address TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        party_id INTEGER,
        invoice_date TEXT,
        total REAL DEFAULT 0,
        status TEXT DEFAULT 'draft',
        vat_rate REAL DEFAULT 0.15,
        vat_amount REAL DEFAULT 0,
        currency_code TEXT DEFAULT 'YER',
        exchange_rate REAL DEFAULT 1.0,
        FOREIGN KEY (party_id) REFERENCES customers(id)
    )''')

    try:
        c.execute("ALTER TABLE invoices ADD COLUMN vat_rate REAL DEFAULT 0.15")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE invoices ADD COLUMN vat_amount REAL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE invoices ADD COLUMN currency_code TEXT DEFAULT 'YER'")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE invoices ADD COLUMN exchange_rate REAL DEFAULT 1.0")
    except sqlite3.OperationalError:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS invoice_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER,
        product_id INTEGER,
        quantity INTEGER,
        unit_price REAL,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS journal_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        description TEXT,
        reference TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS journal_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_id INTEGER,
        account_name TEXT,
        debit REAL DEFAULT 0,
        credit REAL DEFAULT 0,
        currency_code TEXT DEFAULT 'YER',
        exchange_rate REAL DEFAULT 1.0,
        FOREIGN KEY (entry_id) REFERENCES journal_entries(id)
    )''')

    # إضافة أعمدة العملات لجدول journal_lines إذا كان موجوداً مسبقاً
    try:
        c.execute("ALTER TABLE journal_lines ADD COLUMN currency_code TEXT DEFAULT 'YER'")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE journal_lines ADD COLUMN exchange_rate REAL DEFAULT 1.0")
    except sqlite3.OperationalError:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        position TEXT,
        salary REAL,
        join_date TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        date TEXT,
        status TEXT,
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        parent_id INTEGER,
        level INTEGER DEFAULT 1,
        is_debit TEXT DEFAULT 'debit',
        FOREIGN KEY (parent_id) REFERENCES accounts(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS inventory_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        quantity REAL NOT NULL,
        unit_cost REAL NOT NULL,
        batch_date TEXT NOT NULL,
        reference TEXT,
        FOREIGN KEY (product_id) REFERENCES products(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS fifo_consumptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER,
        consumed_qty REAL NOT NULL,
        consumption_date TEXT NOT NULL,
        reference TEXT,
        FOREIGN KEY (batch_id) REFERENCES inventory_batches(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS employee_salaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER UNIQUE,
        basic_salary REAL DEFAULT 0,
        housing_allowance REAL DEFAULT 0,
        transport_allowance REAL DEFAULT 0,
        other_allowances REAL DEFAULT 0,
        deductions REAL DEFAULT 0,
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS payroll_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        month TEXT NOT NULL,
        basic_salary REAL,
        housing_allowance REAL,
        transport_allowance REAL,
        other_allowances REAL,
        total_allowances REAL,
        deductions REAL,
        net_salary REAL,
        journal_entry_id INTEGER,
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS closed_periods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        period_type TEXT NOT NULL,
        period_value TEXT NOT NULL,
        closed_at TEXT NOT NULL,
        closed_by TEXT NOT NULL,
        UNIQUE(period_type, period_value)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS role_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role_id INTEGER,
        module TEXT NOT NULL,
        FOREIGN KEY (role_id) REFERENCES roles(id)
    )''')

    # 🆕 جداول مراكز التكلفة
    c.execute('''CREATE TABLE IF NOT EXISTS cost_centers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        parent_id INTEGER,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (parent_id) REFERENCES cost_centers(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cost_center_allocations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        journal_line_id INTEGER NOT NULL,
        cost_center_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        percentage REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (journal_line_id) REFERENCES journal_lines(id),
        FOREIGN KEY (cost_center_id) REFERENCES cost_centers(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cost_center_budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cost_center_id INTEGER NOT NULL,
        account_id INTEGER NOT NULL,
        fiscal_year INTEGER NOT NULL,
        budget_amount REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cost_center_id) REFERENCES cost_centers(id),
        FOREIGN KEY (account_id) REFERENCES accounts(id),
        UNIQUE(cost_center_id, account_id, fiscal_year)
    )''')

    # 💱 جداول تعدد العملات
    c.execute('''CREATE TABLE IF NOT EXISTS currencies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        symbol TEXT,
        is_base BOOLEAN DEFAULT 0,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS exchange_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_currency TEXT NOT NULL,
        to_currency TEXT NOT NULL,
        rate REAL NOT NULL,
        date TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(from_currency, to_currency, date)
    )''')

    # 🏦 جداول التعاملات البنكية
    c.execute('''CREATE TABLE IF NOT EXISTS bank_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bank_name TEXT NOT NULL,
        account_number TEXT NOT NULL,
        account_name TEXT,
        currency_code TEXT DEFAULT 'YER',
        opening_balance REAL DEFAULT 0,
        current_balance REAL DEFAULT 0,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS bank_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bank_account_id INTEGER NOT NULL,
        transaction_date TEXT NOT NULL,
        description TEXT,
        type TEXT NOT NULL,
        amount REAL NOT NULL,
        reference TEXT,
        journal_line_id INTEGER,
        reconciled BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id),
        FOREIGN KEY (journal_line_id) REFERENCES journal_lines(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS bank_reconciliations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bank_account_id INTEGER NOT NULL,
        reconciliation_date TEXT NOT NULL,
        statement_balance REAL NOT NULL,
        book_balance REAL NOT NULL,
        difference REAL DEFAULT 0,
        status TEXT DEFAULT 'draft',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id)
    )''')

    # 📎 جدول المرفقات
    c.execute('''CREATE TABLE IF NOT EXISTS attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        original_name TEXT NOT NULL,
        file_path TEXT NOT NULL,
        file_size INTEGER,
        file_type TEXT,
        linked_table TEXT,
        linked_id INTEGER,
        uploaded_by TEXT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()

def create_default_admin():
    """إنشاء مستخدم مسؤول افتراضي إذا لم يوجد مستخدمون"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        hashed = bcrypt.hashpw("admin".encode(), bcrypt.gensalt())
        c.execute("INSERT INTO users (username, password, full_name, role) VALUES (?, ?, ?, ?)",
                  ("admin", hashed, "مدير النظام", "admin"))
        conn.commit()
    conn.close()
