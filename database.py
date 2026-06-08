# database.py - قاعدة بيانات نظام حوكمة ERP (PostgreSQL) – إصدار إنتاجي نهائي
import pg8000.native
import bcrypt

# ==========================================
# إعدادات الاتصال بقاعدة بيانات PostgreSQL
# ==========================================
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'user': 'admin',
    'password': '123456',
    'database': 'hokoma_erp'
}

def get_connection():
    """إنشاء اتصال بقاعدة بيانات PostgreSQL باستخدام pg8000"""
    return pg8000.native.Connection(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database']
    )

def init_db():
    """إنشاء جميع جداول النظام إذا لم تكن موجودة"""
    conn = get_connection()

    # ========== 1. المستخدمين (الاعتماد على role_id فقط) ==========
    conn.run('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        full_name TEXT,
        role_id INTEGER NOT NULL,
        FOREIGN KEY (role_id) REFERENCES roles(id)
    )''')

    # ========== 2. المنتجات (أسعار وكميات غير سالبة) ==========
    conn.run('''CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        barcode TEXT UNIQUE,
        category TEXT,
        purchase_price REAL CHECK(purchase_price >= 0),
        selling_price REAL CHECK(selling_price >= 0),
        quantity INTEGER DEFAULT 0 CHECK(quantity >= 0),
        reorder_level INTEGER DEFAULT 10
    )''')

    conn.run('''CREATE TABLE IF NOT EXISTS stock_movements (
        id SERIAL PRIMARY KEY,
        product_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        date TEXT NOT NULL,
        reference TEXT,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )''')

    conn.run('''CREATE TABLE IF NOT EXISTS customers (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        phone TEXT,
        address TEXT
    )''')

    conn.run('''CREATE TABLE IF NOT EXISTS suppliers (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        phone TEXT,
        address TEXT
    )''')

    # ========== 3. الفواتير ==========
    conn.run('''CREATE TABLE IF NOT EXISTS invoices (
        id SERIAL PRIMARY KEY,
        type TEXT NOT NULL,
        invoice_date TEXT NOT NULL DEFAULT CURRENT_DATE,
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

    conn.run('''CREATE TABLE IF NOT EXISTS invoice_items (
        id SERIAL PRIMARY KEY,
        invoice_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
    )''')

    # ========== 4. القيود المحاسبية (حماية من التكرار + منع مدين ودائن معاً) ==========
    conn.run('''CREATE TABLE IF NOT EXISTS journal_entries (
        id SERIAL PRIMARY KEY,
        date TEXT NOT NULL DEFAULT CURRENT_DATE,
        description TEXT NOT NULL,
        reference TEXT UNIQUE
    )''')

    conn.run('''CREATE TABLE IF NOT EXISTS journal_lines (
        id SERIAL PRIMARY KEY,
        entry_id INTEGER NOT NULL,
        account_name TEXT NOT NULL,
        debit REAL DEFAULT 0 CHECK(debit >= 0),
        credit REAL DEFAULT 0 CHECK(credit >= 0),
        currency_code TEXT DEFAULT 'YER',
        exchange_rate REAL DEFAULT 1.0,
        CHECK((debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0)),
        FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE
    )''')

    # ========== 5. الموارد البشرية ==========
    conn.run('''CREATE TABLE IF NOT EXISTS employees (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        position TEXT,
        salary REAL,
        join_date TEXT DEFAULT CURRENT_DATE
    )''')

    conn.run('''CREATE TABLE IF NOT EXISTS attendance (
        id SERIAL PRIMARY KEY,
        employee_id INTEGER NOT NULL,
        date TEXT NOT NULL DEFAULT CURRENT_DATE,
        status TEXT NOT NULL,
        FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
    )''')

    # ========== 6. شجرة الحسابات ==========
    conn.run('''CREATE TABLE IF NOT EXISTS accounts (
        id SERIAL PRIMARY KEY,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        parent_id INTEGER,
        level INTEGER DEFAULT 1,
        is_debit TEXT DEFAULT 'debit',
        is_active INTEGER CHECK(is_active IN (0,1)) DEFAULT 1,
        account_type TEXT CHECK(account_type IN ('Asset','Liability','Equity','Revenue','Expense')),
        FOREIGN KEY (parent_id) REFERENCES accounts(id) ON DELETE SET NULL
    )''')

    # ========== 7. المخزون و FIFO ==========
    conn.run('''CREATE TABLE IF NOT EXISTS inventory_batches (
        id SERIAL PRIMARY KEY,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL CHECK(quantity > 0),
        unit_cost REAL NOT NULL CHECK(unit_cost >= 0),
        batch_date TEXT NOT NULL DEFAULT CURRENT_DATE,
        reference TEXT,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )''')

    conn.run('''CREATE TABLE IF NOT EXISTS fifo_consumptions (
        id SERIAL PRIMARY KEY,
        batch_id INTEGER NOT NULL,
        consumed_qty REAL NOT NULL CHECK(consumed_qty > 0),
        consumption_date TEXT NOT NULL DEFAULT CURRENT_DATE,
        reference TEXT,
        FOREIGN KEY (batch_id) REFERENCES inventory_batches(id) ON DELETE CASCADE
    )''')

    # ========== 8. الرواتب ==========
    conn.run('''CREATE TABLE IF NOT EXISTS employee_salaries (
        id SERIAL PRIMARY KEY,
        employee_id INTEGER UNIQUE NOT NULL,
        basic_salary REAL DEFAULT 0 CHECK(basic_salary >= 0),
        housing_allowance REAL DEFAULT 0 CHECK(housing_allowance >= 0),
        transport_allowance REAL DEFAULT 0 CHECK(transport_allowance >= 0),
        other_allowances REAL DEFAULT 0 CHECK(other_allowances >= 0),
        deductions REAL DEFAULT 0 CHECK(deductions >= 0),
        FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
    )''')

    conn.run('''CREATE TABLE IF NOT EXISTS payroll_runs (
        id SERIAL PRIMARY KEY,
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

    # ========== 9. إغلاق الفترات ==========
    conn.run('''CREATE TABLE IF NOT EXISTS closed_periods (
        id SERIAL PRIMARY KEY,
        period_type TEXT NOT NULL,
        period_value TEXT NOT NULL,
        closed_at TIMESTAMP NOT NULL DEFAULT NOW(),
        closed_by TEXT NOT NULL,
        UNIQUE(period_type, period_value)
    )''')

    # ========== 10. الصلاحيات والأدوار ==========
    conn.run('''CREATE TABLE IF NOT EXISTS roles (
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL
    )''')

    conn.run('''CREATE TABLE IF NOT EXISTS role_permissions (
        id SERIAL PRIMARY KEY,
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

    # ========== 11. سجل التدقيق ==========
    conn.run('''CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        username TEXT,
        action TEXT NOT NULL,
        table_name TEXT NOT NULL,
        record_id INTEGER,
        old_value TEXT,
        new_value TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # ========== 12. مراكز التكلفة ==========
    conn.run('''CREATE TABLE IF NOT EXISTS cost_centers (
        id SERIAL PRIMARY KEY,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        parent_id INTEGER,
        is_active INTEGER CHECK(is_active IN (0,1)) DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (parent_id) REFERENCES cost_centers(id) ON DELETE SET NULL
    )''')

    conn.run('''CREATE TABLE IF NOT EXISTS cost_center_allocations (
        id SERIAL PRIMARY KEY,
        journal_line_id INTEGER NOT NULL,
        cost_center_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        percentage REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (journal_line_id) REFERENCES journal_lines(id) ON DELETE CASCADE,
        FOREIGN KEY (cost_center_id) REFERENCES cost_centers(id) ON DELETE CASCADE
    )''')

    conn.run('''CREATE TABLE IF NOT EXISTS cost_center_budgets (
        id SERIAL PRIMARY KEY,
        cost_center_id INTEGER NOT NULL,
        account_id INTEGER NOT NULL,
        fiscal_year INTEGER NOT NULL,
        budget_amount REAL NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cost_center_id) REFERENCES cost_centers(id) ON DELETE CASCADE,
        FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
        UNIQUE(cost_center_id, account_id, fiscal_year)
    )''')

    # ========== 13. العملات ==========
    conn.run('''CREATE TABLE IF NOT EXISTS currencies (
        id SERIAL PRIMARY KEY,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        symbol TEXT,
        is_base INTEGER CHECK(is_base IN (0,1)) DEFAULT 0,
        is_active INTEGER CHECK(is_active IN (0,1)) DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.run('''CREATE TABLE IF NOT EXISTS exchange_rates (
        id SERIAL PRIMARY KEY,
        from_currency TEXT NOT NULL,
        to_currency TEXT NOT NULL,
        rate REAL NOT NULL CHECK(rate > 0),
        date TEXT NOT NULL DEFAULT CURRENT_DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(from_currency, to_currency, date)
    )''')

    # ========== 14. البنوك ==========
    conn.run('''CREATE TABLE IF NOT EXISTS bank_accounts (
        id SERIAL PRIMARY KEY,
        bank_name TEXT NOT NULL,
        account_number TEXT NOT NULL,
        account_name TEXT,
        currency_code TEXT DEFAULT 'YER',
        opening_balance REAL DEFAULT 0,
        current_balance REAL DEFAULT 0,
        is_active INTEGER CHECK(is_active IN (0,1)) DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.run('''CREATE TABLE IF NOT EXISTS bank_transactions (
        id SERIAL PRIMARY KEY,
        bank_account_id INTEGER NOT NULL,
        transaction_date TEXT NOT NULL DEFAULT CURRENT_DATE,
        description TEXT,
        type TEXT NOT NULL,
        amount REAL NOT NULL,
        reference TEXT,
        journal_line_id INTEGER,
        reconciled INTEGER DEFAULT 0 CHECK(reconciled IN (0,1)),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE,
        FOREIGN KEY (journal_line_id) REFERENCES journal_lines(id) ON DELETE SET NULL
    )''')

    conn.run('''CREATE TABLE IF NOT EXISTS bank_reconciliations (
        id SERIAL PRIMARY KEY,
        bank_account_id INTEGER NOT NULL,
        reconciliation_date TEXT NOT NULL DEFAULT CURRENT_DATE,
        statement_balance REAL NOT NULL,
        book_balance REAL NOT NULL,
        difference REAL DEFAULT 0,
        status TEXT DEFAULT 'draft',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id) ON DELETE CASCADE
    )''')

    # ========== 15. المرفقات ==========
    conn.run('''CREATE TABLE IF NOT EXISTS attachments (
        id SERIAL PRIMARY KEY,
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

    # ========== 16. ضريبة ==========
    conn.run('''CREATE TABLE IF NOT EXISTS vat_config (
        id SERIAL PRIMARY KEY,
        rate REAL NOT NULL DEFAULT 0.15 CHECK(rate >= 0 AND rate <= 1),
        is_active INTEGER CHECK(is_active IN (0,1)) DEFAULT 1,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.run("INSERT INTO vat_config (id, rate, is_active) VALUES (1, 0.15, 1) ON CONFLICT (id) DO NOTHING")

    # ========== 17. السندات والمصروفات والتسويات والافتتاحية وإعادة التقييم ==========
    conn.run('''CREATE TABLE IF NOT EXISTS vouchers (
        id SERIAL PRIMARY KEY,
        type TEXT NOT NULL,
        date TEXT NOT NULL DEFAULT CURRENT_DATE,
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

    conn.run('''CREATE TABLE IF NOT EXISTS expenses (
        id SERIAL PRIMARY KEY,
        date TEXT NOT NULL DEFAULT CURRENT_DATE,
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

    conn.run('''CREATE TABLE IF NOT EXISTS inventory_adjustments (
        id SERIAL PRIMARY KEY,
        date TEXT NOT NULL DEFAULT CURRENT_DATE,
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

    conn.run('''CREATE TABLE IF NOT EXISTS opening_balances (
        id SERIAL PRIMARY KEY,
        entry_date TEXT NOT NULL DEFAULT CURRENT_DATE,
        account_code TEXT NOT NULL,
        account_name TEXT,
        debit REAL DEFAULT 0,
        credit REAL DEFAULT 0,
        journal_entry_id INTEGER,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.run('''CREATE TABLE IF NOT EXISTS opening_inventory (
        id SERIAL PRIMARY KEY,
        entry_date TEXT NOT NULL DEFAULT CURRENT_DATE,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL CHECK(quantity > 0),
        unit_cost REAL NOT NULL CHECK(unit_cost >= 0),
        journal_entry_id INTEGER,
        created_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    )''')

    conn.run('''CREATE TABLE IF NOT EXISTS currency_revaluations (
        id SERIAL PRIMARY KEY,
        date TEXT NOT NULL DEFAULT CURRENT_DATE,
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

    # ========== 18. الفهارس (Indexes) لتحسين الأداء ==========
    conn.run("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_invoices_type ON invoices(type)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_id)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_invoices_supplier ON invoices(supplier_id)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_journal_entries_date ON journal_entries(date)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_journal_lines_account ON journal_lines(account_name)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_stock_movements_product ON stock_movements(product_id)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_inventory_batches_product ON inventory_batches(product_id)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_fifo_consumptions_batch ON fifo_consumptions(batch_id)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_attendance_employee ON attendance(employee_id)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_audit_log_table ON audit_log(table_name)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(username)")
    conn.run("CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp)")

    conn.close()

def create_default_admin():
    """إنشاء مستخدم مسؤول افتراضي بكلمة مرور ثابتة"""
    conn = get_connection()
    # التحقق من وجود مستخدمين
    rows = conn.run("SELECT COUNT(*) FROM users")
    count = rows[0][0] if rows else 0
    if count == 0:
        try:
            # 1. تأكد من وجود دور المدير
            conn.run("INSERT INTO roles (id, name) VALUES (1, 'مدير') ON CONFLICT (id) DO NOTHING")
            # 2. كلمة مرور ثابتة
            hashed = bcrypt.hashpw("admin".encode(), bcrypt.gensalt()).decode()
            conn.run(
                "INSERT INTO users (username, password, full_name, role_id) VALUES (:username, :password, :full_name, :role_id) ON CONFLICT (username) DO NOTHING",
                username="admin",
                password=hashed,
                full_name="مدير النظام",
                role_id=1
            )
        except Exception:
            pass
    conn.close()
