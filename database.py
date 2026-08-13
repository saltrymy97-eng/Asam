# database.py - قاعدة بيانات نظام حوكمة ERP (SQLite) – إصدار إنتاجي نهائي
import sqlite3
import bcrypt
import os

# تغيير مسار قاعدة البيانات إلى مجلد data/ ليتم حفظه مع المشروع
DB_PATH = os.path.join("data", "erp.db")

def get_connection():
    """إنشاء اتصال بقاعدة البيانات مع دعم الوصول القاموسي للصفوف"""
    # التأكد من وجود مجلد data
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """إنشاء جميع جداول النظام إذا لم تكن موجودة"""
    conn = get_connection()
    c = conn.cursor()

    # ========== 1. الصلاحيات والأدوار والمستخدمين ==========
    c.execute('''CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        full_name TEXT,
        role_id INTEGER NOT NULL,
        FOREIGN KEY (role_id) REFERENCES roles(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS role_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role_id INTEGER NOT NULL,
        module TEXT NOT NULL,
        can_view INTEGER DEFAULT 1 CHECK(can_view IN (0,1)),
        can_add INTEGER DEFAULT 0 CHECK(can_add IN (0,1)),
        can_edit INTEGER DEFAULT 0 CHECK(can_edit IN (0,1)),
        can_delete INTEGER DEFAULT 0 CHECK(can_delete IN (0,1)),
        can_approve INTEGER DEFAULT 0 CHECK(can_approve IN (0,1)),
        FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
        UNIQUE(role_id, module)
    )''')

    # ========== 2. شجرة الحسابات (مقدمة لربط القيود بها) ==========
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        parent_id INTEGER,
        level INTEGER DEFAULT 1,
        is_debit TEXT DEFAULT 'debit',
        is_active INTEGER CHECK(is_active IN (0,1)) DEFAULT 1,
        account_type TEXT CHECK(account_type IN ('Asset','Liability','Equity','Revenue','Expense')),
        functional_type TEXT,
        FOREIGN KEY (parent_id) REFERENCES accounts(id) ON DELETE SET NULL
    )''')

    # ========== 3. القيود المحاسبية (محدثة لدعم account_id) ==========
    c.execute('''CREATE TABLE IF NOT EXISTS journal_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_number TEXT UNIQUE,
        date TEXT NOT NULL DEFAULT (date('now')),
        description TEXT NOT NULL,
        reference TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS journal_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_id INTEGER NOT NULL,
        journal_entry_id INTEGER,
        account_id INTEGER,
        account_name TEXT,
        debit REAL DEFAULT 0 CHECK(debit >= 0),
        credit REAL DEFAULT 0 CHECK(credit >= 0),
        currency_code TEXT DEFAULT 'YER',
        exchange_rate REAL DEFAULT 1.0,
        CHECK((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0) OR (debit = 0 AND credit = 0)),
        FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
        FOREIGN KEY (journal_entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE RESTRICT
    )''')

    # ========== 4. المنتجات والمخزون ==========
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        barcode TEXT UNIQUE,
        category TEXT,
        purchase_price REAL CHECK(purchase_price >= 0),
        selling_price REAL CHECK(selling_price >= 0),
        quantity INTEGER DEFAULT 0 CHECK(quantity >= 0),
        reorder_level INTEGER DEFAULT 10
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS stock_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        date TEXT NOT NULL,
        reference TEXT,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS inventory_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL CHECK(quantity > 0),
        unit_cost REAL NOT NULL CHECK(unit_cost >= 0),
        batch_date TEXT NOT NULL DEFAULT (date('now')),
        reference TEXT,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS fifo_consumptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id INTEGER NOT NULL,
        consumed_qty REAL NOT NULL CHECK(consumed_qty > 0),
        consumption_date TEXT NOT NULL DEFAULT (date('now')),
        reference TEXT,
        FOREIGN KEY (batch_id) REFERENCES inventory_batches(id) ON DELETE CASCADE
    )''')

    # ========== 5. العملاء والموردين ==========
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

    # ========== 6. الفواتير ==========
    c.execute('''CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        invoice_date TEXT NOT NULL DEFAULT (date('now')),
        total REAL DEFAULT 0,
        total_base REAL DEFAULT 0,
        status TEXT DEFAULT 'draft',
        vat_rate REAL DEFAULT 0.15,
        vat_amount REAL DEFAULT 0,
        currency_code TEXT DEFAULT 'YER',
        exchange_rate REAL DEFAULT 1.0,
        customer_id INTEGER,
        supplier_id INTEGER,
        reason TEXT,
        reference TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS invoice_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
    )''')

    # ========== 7. الموارد البشرية والرواتب ==========
    c.execute('''CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        position TEXT,
        salary REAL,
        join_date TEXT DEFAULT (date('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        date TEXT NOT NULL DEFAULT (date('now')),
        status TEXT NOT NULL,
        FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS employee_salaries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER UNIQUE NOT NULL,
        basic_salary REAL DEFAULT 0 CHECK(basic_salary >= 0),
        housing_allowance REAL DEFAULT 0 CHECK(housing_allowance >= 0),
        transport_allowance REAL DEFAULT 0 CHECK(transport_allowance >= 0),
        other_allowances REAL DEFAULT 0 CHECK(other_allowances >= 0),
        deductions REAL DEFAULT 0 CHECK(deductions >= 0),
        FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS payroll_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        month TEXT NOT NULL,
        basic_salary REAL,
        housing_allowance REAL,
        transport_allowance REAL,
        other_allowances REAL,
        total_allowances REAL,
        deductions REAL,
        net_salary REAL,
        journal_entry_id INTEGER,
        FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
    )''')

    # ========== 8. إغلاق الفترات ==========
    c.execute('''CREATE TABLE IF NOT EXISTS closed_periods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        period_type TEXT NOT NULL,
        period_value TEXT NOT NULL,
        closed_at TEXT NOT NULL DEFAULT (datetime('now')),
        closed_by TEXT NOT NULL,
        UNIQUE(period_type, period_value)
    )''')

    # ========== 9. سجل التدقيق ==========
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        action TEXT NOT NULL,
        table_name TEXT NOT NULL,
        record_id INTEGER,
        old_value TEXT,
        new_value TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # ========== 10. مراكز التكلفة ==========
    c.execute('''CREATE TABLE IF NOT EXISTS cost_centers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        parent_id INTEGER,
        is_active INTEGER CHECK(is_active IN (0,1)) DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (parent_id) REFERENCES cost_centers(id) ON DELETE SET NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cost_center_allocations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        journal_line_id INTEGER NOT NULL,
        cost_center_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        percentage REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (journal_line_id) REFERENCES journal_lines(id) ON DELETE CASCADE,
        FOREIGN KEY (cost_center_id) REFERENCES cost_centers(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cost_center_budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cost_center_id INTEGER NOT NULL,
        account_id INTEGER NOT NULL,
        fiscal_year INTEGER NOT NULL,
        budget_amount REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cost_center_id) REFERENCES cost_centers(id) ON DELETE CASCADE,
        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
        UNIQUE(cost_center_id, account_id, fiscal_year)
    )''')

    # ========== 11. العملات والبنوك ==========
    c.execute('''CREATE TABLE IF NOT EXISTS currencies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        symbol TEXT,
        is_base INTEGER CHECK(is_base IN (0,1)) DEFAULT 0,
        is_active INTEGER CHECK(is_active IN (0,1)) DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS exchange_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_currency TEXT NOT NULL,
        to_currency TEXT NOT NULL,
        rate REAL NOT NULL CHECK(rate > 0),
        date TEXT NOT NULL DEFAULT (date('now')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(from_currency, to_currency, date)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS bank_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bank_name TEXT NOT NULL,
        account_number TEXT NOT NULL,
        account_code TEXT,
        account_name TEXT,
        currency_code TEXT DEFAULT 'YER',
        opening_balance REAL DEFAULT 0,
        current_balance REAL DEFAULT 0,
        is_active INTEGER CHECK(is_active IN (0,1)) DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # إضافة العمود المفقود بأمان إذا لم يكن موجوداً
    c.execute("PRAGMA table_info(bank_accounts)")
    columns = [col[1] for col in c.fetchall()]
    if "account_code" not in columns:
        c.execute("ALTER TABLE bank_accounts ADD COLUMN account_code TEXT")

    c.execute('''CREATE TABLE IF NOT EXISTS bank_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bank_account_id INTEGER NOT NULL,
        transaction_date TEXT NOT NULL DEFAULT (date('now')),
        description TEXT,
        type TEXT NOT NULL,
        amount REAL NOT NULL,
        reference TEXT,
        journal_id INTEGER,
        journal_line_id INTEGER,
        reconciled INTEGER DEFAULT 0 CHECK(reconciled IN (0,1)),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE
    )''')

    # إضافة العمود journal_id بأمان إذا لم يكن موجوداً في الجدول الحالي
    c.execute("PRAGMA table_info(bank_transactions)")
    columns = [col[1] for col in c.fetchall()]
    if "journal_id" not in columns:
        c.execute("ALTER TABLE bank_transactions ADD COLUMN journal_id INTEGER")

    c.execute('''CREATE TABLE IF NOT EXISTS bank_reconciliations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bank_account_id INTEGER NOT NULL,
        reconciliation_date TEXT NOT NULL DEFAULT (date('now')),
        statement_balance REAL NOT NULL,
        book_balance REAL NOT NULL,
        difference REAL DEFAULT 0,
        status TEXT DEFAULT 'draft',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE
    )''')

    # ========== 12. المرفقات وضريبة القيمة المضافة ==========
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

    c.execute('''CREATE TABLE IF NOT EXISTS vat_config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rate REAL NOT NULL DEFAULT 0.15 CHECK(rate >= 0 AND rate <= 1),
        is_active INTEGER CHECK(is_active IN (0,1)) DEFAULT 1,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute("INSERT OR IGNORE INTO vat_config (id, rate, is_active) VALUES (1, 0.15, 1)")

    # ========== 13. السندات والمصروفات والتسويات ==========
    c.execute('''CREATE TABLE IF NOT EXISTS vouchers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        date TEXT NOT NULL DEFAULT (date('now')),
        party_type TEXT NOT NULL,
        party_id INTEGER,
        amount REAL NOT NULL CHECK(amount > 0),
        account TEXT NOT NULL,
        invoice_id INTEGER,
        journal_entry_id INTEGER,
        reference TEXT,
        notes TEXT,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL DEFAULT (date('now')),
        category TEXT NOT NULL,
        amount REAL NOT NULL CHECK(amount > 0),
        account_code TEXT NOT NULL,
        payment_method TEXT NOT NULL,
        party_type TEXT,
        party_id INTEGER,
        invoice_ref TEXT,
        notes TEXT,
        journal_entry_id INTEGER,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS inventory_adjustments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL DEFAULT (date('now')),
        product_id INTEGER NOT NULL,
        expected_qty REAL NOT NULL,
        actual_qty REAL NOT NULL,
        difference REAL NOT NULL,
        unit_cost REAL,
        total_cost REAL,
        reason TEXT,
        reference TEXT,
        journal_entry_id INTEGER,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS opening_balances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_date TEXT NOT NULL DEFAULT (date('now')),
        account_code TEXT NOT NULL,
        account_name TEXT,
        debit REAL DEFAULT 0,
        credit REAL DEFAULT 0,
        journal_entry_id INTEGER,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS opening_inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_date TEXT NOT NULL DEFAULT (date('now')),
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL CHECK(quantity > 0),
        unit_cost REAL NOT NULL CHECK(unit_cost >= 0),
        journal_entry_id INTEGER,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS currency_revaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL DEFAULT (date('now')),
        account_name TEXT NOT NULL,
        currency_code TEXT NOT NULL,
        old_rate REAL,
        new_rate REAL NOT NULL CHECK(new_rate > 0),
        foreign_balance REAL,
        old_local_value REAL,
        new_local_value REAL,
        difference REAL,
        journal_entry_id INTEGER,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ========== 14. الأصول الثابتة ==========
    c.execute('''CREATE TABLE IF NOT EXISTS fixed_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT DEFAULT 'أثاث ومعدات',
        purchase_date TEXT NOT NULL,
        purchase_cost REAL NOT NULL,
        salvage_value REAL DEFAULT 0,
        useful_life_years INTEGER DEFAULT 5,
        depreciation_method TEXT DEFAULT 'قسط ثابت',
        monthly_depreciation REAL DEFAULT 0,
        accumulated_depreciation REAL DEFAULT 0,
        book_value REAL DEFAULT 0,
        status TEXT DEFAULT 'نشط',
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS depreciation_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id INTEGER,
        entry_date TEXT NOT NULL,
        amount REAL NOT NULL,
        journal_entry_id INTEGER,
        notes TEXT,
        FOREIGN KEY (asset_id) REFERENCES fixed_assets(id)
    )''')

    # ========== 15. CRM (إدارة علاقات العملاء) ==========
    c.execute('''CREATE TABLE IF NOT EXISTS crm_leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        company TEXT,
        phone TEXT,
        email TEXT,
        source TEXT DEFAULT 'أخرى',
        status TEXT DEFAULT 'جديد',
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS crm_opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER,
        title TEXT NOT NULL,
        amount REAL DEFAULT 0,
        stage TEXT DEFAULT 'مؤهل',
        probability INTEGER DEFAULT 50,
        expected_close_date TEXT,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (lead_id) REFERENCES crm_leads(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS crm_interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER,
        type TEXT DEFAULT 'اتصال',
        date TEXT NOT NULL,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (lead_id) REFERENCES crm_leads(id)
    )''')

    # ========== 16. الصندوق (Cash Management) ==========
    c.execute('''CREATE TABLE IF NOT EXISTS cash_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        currency_code TEXT NOT NULL DEFAULT 'YER',
        opening_balance REAL DEFAULT 0.0,
        current_balance REAL DEFAULT 0.0,
        is_active INTEGER DEFAULT 1 CHECK(is_active IN (0,1)),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS cash_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cash_account_id INTEGER NOT NULL,
        transaction_date TEXT NOT NULL,
        description TEXT,
        type TEXT NOT NULL CHECK(type IN ('deposit','withdrawal')),
        amount REAL NOT NULL CHECK(amount > 0),
        reference TEXT,
        journal_line_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cash_account_id) REFERENCES cash_accounts(id)
    )''')

    # ========== 17. الفهارس (Indexes) لتحسين الأداء ==========
    c.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_invoices_type ON invoices(type)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_invoices_supplier ON invoices(supplier_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_journal_entries_date ON journal_entries(date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_journal_lines_account ON journal_lines(account_name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_journal_lines_account_id ON journal_lines(account_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_product ON stock_movements(product_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_inventory_batches_product ON inventory_batches(product_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_fifo_consumptions_batch ON fifo_consumptions(batch_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_attendance_employee ON attendance(employee_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_table ON audit_log(table_name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(username)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_fixed_assets_category ON fixed_assets(category)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_depreciation_entries_asset ON depreciation_entries(asset_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_crm_leads_status ON crm_leads(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_crm_opportunities_lead ON crm_opportunities(lead_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_crm_interactions_lead ON crm_interactions(lead_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_cash_transactions_account ON cash_transactions(cash_account_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_cash_transactions_date ON cash_transactions(transaction_date)")

    conn.commit()
    conn.close()

def create_default_admin():
    """إنشاء مستخدم مسؤول افتراضي بكلمة مرور ثابتة"""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    row = c.fetchone()
    count = row[0] if row else 0
    if count == 0:
        try:
            # 1. تأكد من وجود دور المدير
            c.execute("INSERT OR IGNORE INTO roles (id, name) VALUES (1, 'مدير')")
            # 2. كلمة مرور ثابتة
            hashed = bcrypt.hashpw("admin".encode(), bcrypt.gensalt()).decode()
            c.execute("INSERT INTO users (username, password, full_name, role_id) VALUES (?, ?, ?, ?)",
                      ("admin", hashed, "مدير النظام", 1))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
    conn.close()

# تهيئة قاعدة البيانات تلقائياً عند استيراد الملف
init_db()
create_default_admin()
