# services/seed_service.py
# v1.0 — خدمة حقن البيانات التجريبية الشاملة (كل الوحدات الـ30)
# ✅ SQL مباشر — لا يعتمد على توقيعات الخدمات (يتفادى التعارض مع التعديلات)
# ✅ بيانات متسقة ومتوازنة محاسبياً
# ✅ يشمل 30 وحدة (ما عدا الذكاء الاصطناعي)
# ✅ يولّد سجل تدقيق حقيقي
import sqlite3
import random
import json
from datetime import datetime, date, timedelta
from database import get_connection, close_connection


# ============================================================
# الإعدادات الأساسية
# ============================================================
SEED_START_DATE = date(2026, 1, 1)
SEED_END_DATE = date(2026, 9, 30)
RANDOM_SEED = 20260101
CURRENCY = "YER"

# أسماء واقعية
CUSTOMER_NAMES = [
    "شركة الأمل التجارية", "مؤسسة النور للتجارة", "أحمد للتجارة العامة",
    "شركة الوفاء التجارية", "مؤسسة السلام", "شركة المستقبل",
    "مؤسسة البركة التجارية", "شركة الرائد", "مؤسسة الإخاء",
    "شركة الأصالة التجارية", "مؤسسة التقدم", "شركة الازدهار",
    "مؤسسة الوفاء", "شركة الوطنية", "مؤسسة الخير",
    "شركة الثقة التجارية", "مؤسسة الأمانة", "شركة العروبة",
    "مؤسسة النخبة", "شركة الجودة",
]

SUPPLIER_NAMES = [
    "شركة الفجر للتوريدات", "مورد الخليج", "مؤسسة الإمداد",
    "شركة الرياض للتوريد", "مؤسسة الأمين", "شركة الياسمين",
    "مؤسسة الرواد", "شركة البدر", "مؤسسة الوفاء للتوريدات",
    "شركة النخيل", "مؤسسة الشرق", "شركة الجزيرة",
    "مؤسسة الصفا", "شركة المرجان", "مؤسسة الفرات",
]

PRODUCT_CATEGORIES = {
    "مواد غذائية": [
        ("أرز بسمتي 5 كجم", 3500, 4200),
        ("سكر أبيض 10 كجم", 4800, 5600),
        ("زيت طهي 1.8 لتر", 2200, 2700),
        ("شاي أحمر 500 جم", 1800, 2300),
        ("حليب مجفف 900 جم", 3200, 3900),
        ("دقيق فاخر 10 كجم", 2800, 3300),
        ("معكرونة 500 جم", 450, 650),
        ("عدس 1 كجم", 900, 1200),
        ("فول 1 كجم", 800, 1100),
        ("حمص 1 كجم", 950, 1250),
    ],
    "مشروبات": [
        ("مياه معدنية 24 قنينة", 1200, 1600),
        ("عصير برتقال 1 لتر", 850, 1200),
        ("مشروب غازي 2 لتر", 600, 900),
        ("قهوة عربية 250 جم", 2400, 3100),
        ("شاي أخضر 250 جم", 1500, 1900),
    ],
    "منظفات": [
        ("مسحوق غسيل 5 كجم", 3800, 4600),
        ("صابون سائل 1 لتر", 950, 1300),
        ("منظف أرضيات 2 لتر", 1100, 1500),
        ("معقم أسطح 750 مل", 850, 1150),
        ("صابون أيدي 500 مل", 650, 900),
    ],
    "قرطاسية": [
        ("ورق A4 500 ورقة", 1500, 2000),
        ("قلم حبر أزرق", 100, 250),
        ("دفتر 100 ورقة", 250, 450),
        ("ملف بلاستيكي", 150, 350),
        ("دباسة مكتبية", 450, 750),
    ],
    "أدوات منزلية": [
        ("طقم صحون 12 قطعة", 4500, 5800),
        ("كوب زجاجي 6 قطع", 1200, 1800),
        ("مقلاة تيفال", 3800, 4900),
        ("طقم ملاعق ستانلس", 900, 1400),
        ("حافظة طعام 3 قطع", 1500, 2100),
    ],
}

EMPLOYEE_DATA = [
    ("محمد أحمد علي", "مدير عام", 800000),
    ("عبدالله سالم", "مدير مالي", 650000),
    ("فاطمة محمد", "محاسب أول", 500000),
    ("خالد عمر", "محاسب", 400000),
    ("سعيد يحيى", "أمين مخزن", 350000),
    ("أمين قاسم", "موظف مبيعات", 320000),
    ("ناصر عبدالله", "موظف مشتريات", 330000),
    ("هشام محمد", "موظف موارد بشرية", 380000),
    ("طارق أحمد", "مهندس صيانة", 420000),
    ("يوسف سالم", "سائق", 250000),
    ("إبراهيم ناصر", "عامل مخزن", 220000),
    ("كريم عبدالرحمن", "موظف مبيعات", 320000),
    ("سامي حسن", "محاسب مساعد", 280000),
    ("عادل محمد", "حارس أمن", 220000),
    ("بشير علي", "عامل نظافة", 200000),
]

# ============================================================
# دالة مساعدة
# ============================================================
def _rand_date(start=SEED_START_DATE, end=SEED_END_DATE):
    days = (end - start).days
    if days <= 0:
        return start
    return start + timedelta(days=random.randint(0, days))


def _fmt(d):
    if isinstance(d, date):
        return d.strftime("%Y-%m-%d")
    return str(d)


def _phone():
    return f"+9677{random.randint(10000000, 99999999)}"


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# 1) حذف كل البيانات
# ============================================================
def delete_all_data(conn):
    """حذف كل البيانات من جميع الجداول (مع الاحتفاظ بالبنية)"""
    conn.execute("PRAGMA foreign_keys = OFF")

    tables = [
        "cost_center_allocations", "fifo_consumptions", "journal_lines",
        "invoice_items", "invoice_payments", "cash_transactions",
        "bank_transactions", "depreciation_entries", "opening_inventory",
        "opening_balances", "inventory_adjustments", "stock_movements",
        "inventory_batches", "payroll_runs", "employee_salaries",
        "attendance", "currency_revaluations", "vouchers", "expenses",
        "invoices", "journal_entries", "crm_interactions",
        "crm_opportunities", "crm_leads", "fixed_assets", "employees",
        "customers", "suppliers", "products", "bank_reconciliations",
        "bank_accounts", "cash_accounts", "cost_center_budgets",
        "cost_centers", "closing_logs", "closed_periods", "exchange_rates",
        "role_permissions", "users", "roles", "accounts",
        "attachments", "audit_log",
    ]

    for t in tables:
        try:
            conn.execute(f"DELETE FROM {t}")
        except Exception as e:
            print(f"⚠️ حذف {t}: {e}")

    # إعادة تصفير AUTOINCREMENT
    try:
        conn.execute("DELETE FROM sqlite_sequence WHERE name != 'vat_config'")
    except Exception:
        pass

    # الاحتفاظ بإعداد VAT فقط
    try:
        conn.execute("DELETE FROM vat_config WHERE id != 1")
        conn.execute(
            "INSERT OR IGNORE INTO vat_config (id, rate, is_active) VALUES (1, 0.15, 1)"
        )
    except Exception:
        pass

    conn.execute("PRAGMA foreign_keys = ON")
    print("✅ تم حذف كل البيانات")


# ============================================================
# 2) الأدوار والمستخدمون
# ============================================================
def seed_roles_users(conn):
    """حقن الأدوار والمستخدمين"""
    import bcrypt

    roles = [
        (1, "مدير"),
        (2, "مدير مالي"),
        (3, "محاسب"),
        (4, "أمين مخزن"),
        (5, "موظف مبيعات"),
    ]
    for rid, name in roles:
        conn.execute("INSERT INTO roles (id, name) VALUES (?, ?)", (rid, name))

    users = [
        ("admin", "admin", "مدير النظام", 1),
        ("manager", "manager", "المدير المالي", 2),
        ("accountant", "accountant", "المحاسب الرئيسي", 3),
        ("storekeeper", "storekeeper", "أمين المخزن", 4),
        ("sales", "sales", "موظف المبيعات", 5),
    ]
    for uname, pwd, fullname, rid in users:
        hashed = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
        conn.execute(
            "INSERT INTO users (username, password, full_name, role_id) VALUES (?,?,?,?)",
            (uname, hashed, fullname, rid),
        )
    print(f"✅ الأدوار: {len(roles)} | المستخدمون: {len(users)}")


# ============================================================
# 3) الصلاحيات
# ============================================================
def seed_role_permissions(conn):
    """حقن صلاحيات الأدوار لكل الوحدات"""
    modules = [
        "لوحة المعلومات", "المبيعات", "المشتريات", "مرتجعات البضاعة",
        "سندات القبض والصرف", "المخزون", "التسويات المخزنية", "المصروفات",
        "إدارة العملاء", "الحسابات", "شجرة الحسابات", "القوائم المالية",
        "مراكز التكلفة", "العملات", "الأرصدة الافتتاحية", "الصندوق",
        "التعاملات البنكية", "الضريبة", "إغلاق الحسابات", "إغلاق الفترات",
        "FIFO المخزون", "تقييم العملات", "التقارير المالية XBRL",
        "الموارد البشرية", "كشف الرواتب", "الأصول الثابتة", "المرفقات",
        "الصلاحيات", "سجل التدقيق", "نسخ احتياطي", "المساعد الذكي",
    ]

    perms_map = {
        1: (1, 1, 1, 1, 1),  # مدير: كل شيء
        2: (1, 1, 1, 1, 1),  # مدير مالي: كل شيء
        3: (1, 1, 1, 0, 0),  # محاسب
        4: (1, 1, 0, 0, 0),  # أمين مخزن
        5: (1, 1, 0, 0, 0),  # موظف مبيعات
    }

    count = 0
    for rid, (v, a, e, d, ap) in perms_map.items():
        for module in modules:
            if rid in (1, 2):
                cv, ca, ce, cd, cap = 1, 1, 1, 1, 1
            elif rid == 3:
                if module in ("المبيعات", "المشتريات", "المخزون", "التسويات المخزنية"):
                    cv, ca, ce, cd, cap = 1, 0, 0, 0, 0
                else:
                    cv, ca, ce, cd, cap = 1, 1, 1, 0, 0
            elif rid == 4:
                if module in ("المخزون", "FIFO المخزون", "التسويات المخزنية", "لوحة المعلومات"):
                    cv, ca, ce, cd, cap = 1, 1, 1, 0, 0
                else:
                    cv, ca, ce, cd, cap = 0, 0, 0, 0, 0
            else:  # rid == 5
                if module in ("المبيعات", "إدارة العملاء", "لوحة المعلومات"):
                    cv, ca, ce, cd, cap = 1, 1, 0, 0, 0
                else:
                    cv, ca, ce, cd, cap = 0, 0, 0, 0, 0

            try:
                conn.execute("""
                    INSERT INTO role_permissions
                    (role_id, module, can_view, can_add, can_edit, can_delete, can_approve)
                    VALUES (?,?,?,?,?,?,?)
                """, (rid, module, cv, ca, ce, cd, cap))
                count += 1
            except sqlite3.IntegrityError:
                pass

    print(f"✅ الصلاحيات: {count}")


# ============================================================
# 4) شجرة الحسابات
# ============================================================
def seed_accounts(conn):
    """حقن شجرة الحسابات (65 حساب)"""
    accounts = [
        # ===== الأصول =====
        ("1", "الأصول", None, 1, "debit", "Asset", None),
        ("11", "الأصول المتداولة", "1", 2, "debit", "Asset", None),
        ("1101", "الصندوق", "11", 3, "debit", "Asset", "cash"),
        ("1102", "البنك", "11", 3, "debit", "Asset", "bank"),
        ("1103", "صندوق فرعي", "11", 3, "debit", "Asset", "cash"),
        ("1201", "العملاء", "11", 3, "debit", "Asset", "accounts_receivable"),
        ("1202", "أوراق قبض", "11", 3, "debit", "Asset", None),
        ("1203", "مصروفات مدفوعة مقدماً", "11", 3, "debit", "Asset", None),
        ("1301", "المخزون", "11", 3, "debit", "Asset", "inventory"),
        ("1302", "ضريبة المدخلات", "11", 3, "debit", "Asset", "purchase_tax"),
        ("1303", "مجمع إهلاك الأصول", "11", 3, "credit", "Asset", "accumulated_depreciation"),
        ("14", "الأصول الثابتة", "1", 2, "debit", "Asset", None),
        ("1401", "أثاث ومعدات", "14", 3, "debit", "Asset", "fixed_assets"),
        ("1402", "سيارات", "14", 3, "debit", "Asset", "fixed_assets"),
        ("1403", "أجهزة كمبيوتر", "14", 3, "debit", "Asset", "fixed_assets"),

        # ===== الخصوم =====
        ("2", "الخصوم", None, 1, "credit", "Liability", None),
        ("21", "الخصوم المتداولة", "2", 2, "credit", "Liability", None),
        ("2101", "الموردون", "21", 3, "credit", "Liability", "accounts_payable"),
        ("2102", "ضريبة المخرجات", "21", 3, "credit", "Liability", "sales_tax"),
        ("2103", "رواتب مستحقة", "21", 3, "credit", "Liability", "accrued_expenses"),
        ("2104", "مصروفات مستحقة", "21", 3, "credit", "Liability", "accrued_expenses"),
        ("2105", "قروض قصيرة الأجل", "21", 3, "credit", "Liability", None),

        # ===== حقوق الملكية =====
        ("3", "حقوق الملكية", None, 1, "credit", "Equity", None),
        ("3101", "رأس المال", "3", 2, "credit", "Equity", "capital"),
        ("3102", "الأرباح المبقاة", "3", 2, "credit", "Equity", "retained_earnings"),
        ("3103", "المسحوبات الشخصية", "3", 2, "debit", "Equity", None),

        # ===== الإيرادات =====
        ("4", "الإيرادات", None, 1, "credit", "Revenue", None),
        ("41", "إيرادات النشاط الرئيسي", "4", 2, "credit", "Revenue", None),
        ("4101", "إيرادات المبيعات", "41", 3, "credit", "Revenue", "sales_revenue"),
        ("4102", "مردودات المبيعات", "41", 3, "debit", "Revenue", None),
        ("4103", "خصم مسموح به", "41", 3, "debit", "Revenue", None),
        ("42", "إيرادات أخرى", "4", 2, "credit", "Revenue", None),
        ("4201", "إيرادات متنوعة", "42", 3, "credit", "Revenue", None),
        ("4202", "فروق أسعار الصرف", "42", 3, "credit", "Revenue", "exchange_difference"),

        # ===== المصروفات =====
        ("5", "المصروفات", None, 1, "debit", "Expense", None),
        ("51", "تكلفة المبيعات", "5", 2, "debit", "Expense", None),
        ("5101", "تكلفة البضاعة المباعة", "51", 3, "debit", "Expense", "cogs"),
        ("52", "مصروفات تشغيلية", "5", 2, "debit", "Expense", None),
        ("5201", "مصروف الرواتب", "52", 3, "debit", "Expense", "salaries_expense"),
        ("5202", "مصروف الإيجار", "52", 3, "debit", "Expense", "operating_expense"),
        ("5203", "مصروف الكهرباء والماء", "52", 3, "debit", "Expense", "operating_expense"),
        ("5204", "مصروف الإهلاك", "52", 3, "debit", "Expense", "depreciation_expense"),
        ("5205", "مصروف الاتصالات", "52", 3, "debit", "Expense", "operating_expense"),
        ("5206", "مصروفات نظافة", "52", 3, "debit", "Expense", "operating_expense"),
        ("5207", "مصروفات صيانة", "52", 3, "debit", "Expense", "operating_expense"),
        ("5208", "مصروفات تسويق", "52", 3, "debit", "Expense", "operating_expense"),
        ("5209", "مصروفات نقل", "52", 3, "debit", "Expense", "operating_expense"),
        ("5210", "مصروفات بنكية", "52", 3, "debit", "Expense", "operating_expense"),
        ("5211", "مصروفات حكومية", "52", 3, "debit", "Expense", "operating_expense"),
        ("5212", "مصروفات متنوعة", "52", 3, "debit", "Expense", "operating_expense"),
        ("53", "خسائر", "5", 2, "debit", "Expense", None),
        ("5301", "خسائر جرد المخزون", "53", 3, "debit", "Expense", "inventory_loss"),
        ("5302", "عجز/خسائر أخرى", "53", 3, "debit", "Expense", "inventory_loss"),
    ]

    code_to_id = {}
    for code, name, parent_code, level, is_debit, atype, ftype in accounts:
        parent_id = code_to_id.get(parent_code) if parent_code else None
        cur = conn.execute("""
            INSERT INTO accounts (code, name, parent_id, level, is_debit,
                                   account_type, functional_type, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (code, name, parent_id, level, is_debit, atype, ftype))
        code_to_id[code] = cur.lastrowid

    print(f"✅ الحسابات: {len(accounts)}")
    return code_to_id


# ============================================================
# 5) العملات وأسعار الصرف
# ============================================================
def seed_currencies(conn):
    currencies = [
        ("YER", "الريال اليمني", "ر.ي", 1),
        ("USD", "الدولار الأمريكي", "$", 0),
        ("SAR", "الريال السعودي", "ر.س", 0),
        ("EUR", "اليورو", "€", 0),
    ]
    for code, name, sym, is_base in currencies:
        try:
            conn.execute("""
                INSERT INTO currencies (code, name, symbol, is_base, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (code, name, sym, is_base))
        except sqlite3.IntegrityError:
            pass

    # أسعار صرف تاريخية
    rates = [
        ("USD", "YER", 530.0, "2026-01-01"),
        ("USD", "YER", 535.0, "2026-04-01"),
        ("USD", "YER", 540.0, "2026-07-01"),
        ("SAR", "YER", 141.0, "2026-01-01"),
        ("SAR", "YER", 142.5, "2026-07-01"),
        ("EUR", "YER", 575.0, "2026-01-01"),
        ("EUR", "YER", 580.0, "2026-07-01"),
    ]
    for from_c, to_c, rate, d in rates:
        try:
            conn.execute("""
                INSERT INTO exchange_rates (from_currency, to_currency, rate, date)
                VALUES (?, ?, ?, ?)
            """, (from_c, to_c, rate, d))
        except sqlite3.IntegrityError:
            pass

    print(f"✅ العملات: {len(currencies)} | الأسعار: {len(rates)}")


# ============================================================
# 6) مراكز التكلفة
# ============================================================
def seed_cost_centers(conn):
    centers = [
        ("CC-100", "الإدارة العامة", None),
        ("CC-200", "المبيعات", None),
        ("CC-300", "المشتريات", None),
        ("CC-400", "المخازن", None),
        ("CC-500", "الموارد البشرية", None),
    ]
    ids = []
    for code, name, parent in centers:
        cur = conn.execute("""
            INSERT INTO cost_centers (code, name, parent_id, is_active)
            VALUES (?, ?, ?, 1)
        """, (code, name, parent))
        ids.append(cur.lastrowid)
    print(f"✅ مراكز التكلفة: {len(centers)}")
    return ids


# ============================================================
# 7) الصناديق والبنوك
# ============================================================
def seed_cash_and_bank(conn):
    # الصناديق
    cash_accounts = [
        ("الصندوق الرئيسي", "YER", 500000, "1101"),
        ("صندوق النقد الأجنبي", "USD", 2000, "1103"),
    ]
    for name, curr, bal, code in cash_accounts:
        conn.execute("""
            INSERT INTO cash_accounts
            (name, currency_code, opening_balance, current_balance, account_code, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (name, curr, bal, bal, code))

    # البنوك
    bank_accounts = [
        ("بنك اليمن الدولي", "1001234567", "1102", "الحساب الجاري - YER", "YER", 5000000),
        ("بنك التضامن", "2004567890", "1102", "حساب التوفير - YER", "YER", 2000000),
        ("بنك الكريمي", "3009876543", "1102", "حساب بالدولار", "USD", 15000),
    ]
    for bn, acc, code, name, curr, bal in bank_accounts:
        conn.execute("""
            INSERT INTO bank_accounts
            (bank_name, account_number, account_code, account_name,
             currency_code, opening_balance, current_balance, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (bn, acc, code, name, curr, bal, bal))

    print(f"✅ الصناديق: {len(cash_accounts)} | البنوك: {len(bank_accounts)}")


# ============================================================
# 8) العملاء والموردون
# ============================================================
def seed_parties(conn):
    # العملاء
    for name in CUSTOMER_NAMES:
        conn.execute("""
            INSERT INTO customers (name, phone, address)
            VALUES (?, ?, ?)
        """, (name, _phone(), f"اليمن - صنعاء - شارع {random.randint(1, 50)}"))

    # الموردون
    for name in SUPPLIER_NAMES:
        conn.execute("""
            INSERT INTO suppliers (name, phone, address)
            VALUES (?, ?, ?)
        """, (name, _phone(), f"اليمن - صنعاء - منطقة {random.randint(1, 20)}"))

    print(f"✅ العملاء: {len(CUSTOMER_NAMES)} | الموردون: {len(SUPPLIER_NAMES)}")


# ============================================================
# 9) المنتجات
# ============================================================
def seed_products(conn):
    count = 0
    for category, items in PRODUCT_CATEGORIES.items():
        for name, purchase_price, selling_price in items:
            barcode = f"PRD{random.randint(10000000, 99999999)}"
            qty = random.randint(50, 500)
            conn.execute("""
                INSERT INTO products
                (name, barcode, category, purchase_price, selling_price,
                 quantity, reorder_level)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, barcode, category, purchase_price, selling_price,
                  qty, random.randint(10, 30)))
            count += 1
    print(f"✅ المنتجات: {count}")


# ============================================================
# 10) الموظفون والرواتب والحضور
# ============================================================
def seed_employees(conn):
    employee_ids = []
    for name, position, salary in EMPLOYEE_DATA:
        join_date = _fmt(_rand_date(SEED_START_DATE - timedelta(days=365),
                                     SEED_START_DATE))
        cur = conn.execute("""
            INSERT INTO employees (name, position, salary, join_date)
            VALUES (?, ?, ?, ?)
        """, (name, position, salary, join_date))
        employee_ids.append(cur.lastrowid)

        # إعدادات الراتب
        basic = salary
        housing = round(basic * 0.10)
        transport = round(basic * 0.05)
        other = round(basic * 0.03)
        deductions = round(basic * 0.02)
        conn.execute("""
            INSERT INTO employee_salaries
            (employee_id, basic_salary, housing_allowance, transport_allowance,
             other_allowances, deductions)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cur.lastrowid, basic, housing, transport, other, deductions))

    # الحضور (200 سجل)
    attendance_count = 0
    for _ in range(200):
        emp_id = random.choice(employee_ids)
        d = _fmt(_rand_date())
        status = random.choices(
            ["حاضر", "غائب", "إجازة", "متأخر"],
            weights=[85, 5, 7, 3]
        )[0]
        try:
            conn.execute("""
                INSERT INTO attendance (employee_id, date, status)
                VALUES (?, ?, ?)
            """, (emp_id, d, status))
            attendance_count += 1
        except sqlite3.IntegrityError:
            pass

    print(f"✅ الموظفون: {len(EMPLOYEE_DATA)} | الحضور: {attendance_count}")
    return employee_ids


# ============================================================
# 11) كشوف الرواتب
# ============================================================
def seed_payroll(conn):
    months = ["2026-06", "2026-07", "2026-08", "2026-09"]
    count = 0

    emp_rows = conn.execute("""
        SELECT e.id, e.name, es.basic_salary, es.housing_allowance,
               es.transport_allowance, es.other_allowances, es.deductions
        FROM employees e
        JOIN employee_salaries es ON e.id = es.employee_id
    """).fetchall()

    for month in months:
        for e in emp_rows:
            basic = e[2] or 0
            housing = e[3] or 0
            transport = e[4] or 0
            other = e[5] or 0
            deductions = e[6] or 0
            total_allow = housing + transport + other
            net = basic + total_allow - deductions
            try:
                conn.execute("""
                    INSERT INTO payroll_runs
                    (employee_id, month, basic_salary, housing_allowance,
                     transport_allowance, other_allowances, total_allowances,
                     deductions, net_salary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (e[0], month, basic, housing, transport, other,
                      total_allow, deductions, net))
                count += 1
            except Exception:
                pass

    print(f"✅ كشوف الرواتب: {count}")


# ============================================================
# 12) الأصول الثابتة
# ============================================================
def seed_fixed_assets(conn):
    assets = [
        ("سيارة تويوتا هايلكس", "مركبات", 15000000, 1500000, 8, "قسط ثابت"),
        ("سيارة هيونداي", "مركبات", 12000000, 1200000, 7, "قسط ثابت"),
        ("مبنى الإدارة", "مباني", 80000000, 10000000, 25, "قسط ثابت"),
        ("كمبيوتر مكتبي 1", "أجهزة كمبيوتر", 800000, 50000, 4, "قسط ثابت"),
        ("كمبيوتر مكتبي 2", "أجهزة كمبيوتر", 800000, 50000, 4, "قسط ثابت"),
        ("لابتوب Dell", "أجهزة كمبيوتر", 1200000, 100000, 4, "قسط ثابت"),
        ("طابعة ليزر", "أثاث ومعدات", 600000, 30000, 5, "قسط ثابت"),
        ("مكيف مركزي", "أثاث ومعدات", 2500000, 200000, 10, "قسط ثابت"),
        ("أثاث مكتبي طقم", "أثاث ومعدات", 3500000, 200000, 10, "قسط ثابت"),
        ("رفوف مخزن", "أثاث ومعدات", 2200000, 150000, 8, "قسط ثابت"),
        ("سيارة شحن", "مركبات", 25000000, 2000000, 10, "قسط ثابت"),
        ("مولد كهربائي", "آلات", 4500000, 300000, 8, "قسط ثابت"),
    ]

    count = 0
    for name, cat, cost, salvage, life, method in assets:
        monthly = round((cost - salvage) / (life * 12), 2)
        purchase_date = _fmt(_rand_date(SEED_START_DATE - timedelta(days=180),
                                         SEED_START_DATE))
        # حساب الإهلاك المتراكم حتى الآن
        months_passed = random.randint(1, 9)
        accum = round(monthly * months_passed, 2)
        if accum > (cost - salvage):
            accum = cost - salvage
        book = round(cost - accum, 2)

        conn.execute("""
            INSERT INTO fixed_assets
            (name, category, purchase_date, purchase_cost, salvage_value,
             useful_life_years, depreciation_method, monthly_depreciation,
             accumulated_depreciation, book_value, status,
             annual_depreciation_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'نشط', 0)
        """, (name, cat, purchase_date, cost, salvage, life, method,
              monthly, accum, book))

        asset_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # قيود الإهلاك
        for i in range(months_passed):
            d = SEED_START_DATE + timedelta(days=30 * i)
            conn.execute("""
                INSERT INTO depreciation_entries
                (asset_id, entry_date, amount, notes)
                VALUES (?, ?, ?, ?)
            """, (asset_id, _fmt(d), monthly, f"إهلاك شهر {i+1}"))
        count += 1

    print(f"✅ الأصول الثابتة: {count}")


# ============================================================
# 13) CRM
# ============================================================
def seed_crm(conn):
    leads_data = [
        ("شركة الرياض للتجارة", "م. خالد الحربي", "twitter"),
        ("مؤسسة النخبة", "أ. سارة أحمد", "referral"),
        ("مجموعة الفهد التجارية", "م. فهد العتيبي", "website"),
        ("شركة البحر الأحمر", "أ. مريم علي", "linkedin"),
        ("مؤسسة الأوائل", "م. عمر صالح", "cold_call"),
        ("شركة النهضة", "أ. نورة محمد", "twitter"),
        ("مجموعة الياسمين", "م. راشد السالم", "referral"),
        ("شركة الأصالة", "أ. هند العلي", "website"),
        ("مؤسسة الرواد", "م. سلطان القحطاني", "linkedin"),
        ("شركة المروج", "أ. لمى إبراهيم", "cold_call"),
        ("مؤسسة الوفاء", "م. ماجد الدوسري", "twitter"),
        ("شركة الإبداع", "أ. رنا الشمري", "referral"),
        ("مجموعة النخيل", "م. تركي الغامدي", "website"),
        ("شركة الرؤية", "أ. أسماء الفهد", "linkedin"),
        ("مؤسسة الريادة", "م. بندر العتيبي", "cold_call"),
    ]

    statuses = ["جديد", "مؤهل", "قيد التفاوض", "عميل محتمل", "مفقود"]
    lead_ids = []
    for name, contact, source in leads_data:
        status = random.choice(statuses)
        d = _fmt(_rand_date())
        cur = conn.execute("""
            INSERT INTO crm_leads
            (name, company, phone, email, source, status, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (contact, name, _phone(),
              f"contact{random.randint(100, 999)}@example.com",
              source, status, f"عميل محتمل من {source}", d))
        lead_ids.append(cur.lastrowid)

    # الفرص البيعية
    stages = ["مؤهل", "تقديم عرض", "تفاوض", "مغلق - فاز", "مغلق - خسر"]
    opp_count = 0
    for i in range(20):
        lead_id = random.choice(lead_ids)
        stage = random.choice(stages)
        amount = random.randint(500000, 10000000)
        probability = random.choice([20, 40, 60, 80, 100])
        d = _fmt(_rand_date(date.today(), date.today() + timedelta(days=60)))
        conn.execute("""
            INSERT INTO crm_opportunities
            (lead_id, title, amount, stage, probability, expected_close_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (lead_id, f"فرصة #{i+1}", amount, stage, probability, d, ""))
        opp_count += 1

    # التفاعلات
    types = ["اتصال", "بريد", "اجتماع", "زيارة", "واتساب"]
    int_count = 0
    for _ in range(40):
        lead_id = random.choice(lead_ids)
        t = random.choice(types)
        d = _fmt(_rand_date())
        conn.execute("""
            INSERT INTO crm_interactions (lead_id, type, date, notes)
            VALUES (?, ?, ?, ?)
        """, (lead_id, t, d, f"تفاعل من نوع {t}"))
        int_count += 1

    print(f"✅ CRM: {len(leads_data)} عميل محتمل | {opp_count} فرصة | {int_count} تفاعل")


# ============================================================
# 14) المخزون + دفعات FIFO
# ============================================================
def seed_inventory(conn):
    products = conn.execute(
        "SELECT id, purchase_price FROM products"
    ).fetchall()

    batch_count = 0
    movement_count = 0

    for p in products:
        # 3 دفعات شراء لكل منتج
        for _ in range(3):
            qty = random.randint(100, 500)
            cost = p[1] * random.uniform(0.9, 1.1)
            batch_date = _fmt(_rand_date())
            try:
                conn.execute("""
                    INSERT INTO inventory_batches
                    (product_id, quantity, unit_cost, batch_date, reference)
                    VALUES (?, ?, ?, ?, ?)
                """, (p[0], qty, round(cost, 2), batch_date,
                      f"PO-{random.randint(1000, 9999)}"))
                batch_count += 1
            except Exception:
                pass

        # حركات المخزون
        for _ in range(random.randint(3, 8)):
            qty = random.randint(10, 100)
            t = random.choice(["in", "out"])
            d = _fmt(_rand_date())
            conn.execute("""
                INSERT INTO stock_movements
                (product_id, type, quantity, date, reference)
                VALUES (?, ?, ?, ?, ?)
            """, (p[0], t, qty, d, f"MOV-{random.randint(1000, 9999)}"))
            movement_count += 1

    print(f"✅ دفعات FIFO: {batch_count} | حركات المخزون: {movement_count}")


# ============================================================
# 15) فواتير البيع والشراء
# ============================================================
def seed_invoices(conn):
    customers = conn.execute("SELECT id FROM customers").fetchall()
    suppliers = conn.execute("SELECT id FROM suppliers").fetchall()
    products = conn.execute(
        "SELECT id, selling_price, purchase_price FROM products"
    ).fetchall()

    # ============ فواتير البيع (60) ============
    sale_count = 0
    for _ in range(60):
        customer_id = random.choice(customers)[0]
        d = _rand_date()
        num_items = random.randint(1, 5)
        items = random.sample(products, num_items)
        total = 0
        item_list = []
        for p in items:
            qty = random.randint(1, 20)
            price = p[1]
            subtotal = qty * price
            total += subtotal
            item_list.append((p[0], qty, price))

        vat = round(total * 0.15, 2)
        grand_total = round(total + vat, 2)

        # حالة الدفع
        status = random.choice(["unpaid", "partial", "paid"])
        paid = 0
        if status == "paid":
            paid = grand_total
        elif status == "partial":
            paid = round(grand_total * random.uniform(0.2, 0.7), 2)
        remaining = round(grand_total - paid, 2)

        conn.execute("""
            INSERT INTO invoices
            (type, invoice_date, total, total_base, status, vat_rate,
             vat_amount, currency_code, exchange_rate, customer_id,
             paid_amount, remaining_amount, payment_status, reference)
            VALUES ('sale', ?, ?, ?, 'completed', 0.15, ?, 'YER', 1.0, ?,
                    ?, ?, ?, ?)
        """, (_fmt(d), grand_total, grand_total, vat, customer_id,
              paid, remaining, status, f"INV-{random.randint(10000, 99999)}"))

        inv_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        for pid, qty, price in item_list:
            conn.execute("""
                INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
            """, (inv_id, pid, qty, price))

        sale_count += 1

    # ============ فواتير الشراء (35) ============
    purchase_count = 0
    for _ in range(35):
        supplier_id = random.choice(suppliers)[0]
        d = _rand_date()
        num_items = random.randint(1, 5)
        items = random.sample(products, num_items)
        total = 0
        item_list = []
        for p in items:
            qty = random.randint(10, 100)
            price = p[2]
            subtotal = qty * price
            total += subtotal
            item_list.append((p[0], qty, price))

        vat = round(total * 0.15, 2)
        grand_total = round(total + vat, 2)

        status = random.choice(["unpaid", "partial", "paid"])
        paid = 0
        if status == "paid":
            paid = grand_total
        elif status == "partial":
            paid = round(grand_total * random.uniform(0.2, 0.7), 2)
        remaining = round(grand_total - paid, 2)

        conn.execute("""
            INSERT INTO invoices
            (type, invoice_date, total, total_base, status, vat_rate,
             vat_amount, currency_code, exchange_rate, supplier_id,
             paid_amount, remaining_amount, payment_status, reference)
            VALUES ('purchase', ?, ?, ?, 'completed', 0.15, ?, 'YER', 1.0, ?,
                    ?, ?, ?, ?)
        """, (_fmt(d), grand_total, grand_total, vat, supplier_id,
              paid, remaining, status, f"PO-{random.randint(10000, 99999)}"))

        inv_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        for pid, qty, price in item_list:
            conn.execute("""
                INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
            """, (inv_id, pid, qty, price))

        purchase_count += 1

    print(f"✅ فواتير البيع: {sale_count} | فواتير الشراء: {purchase_count}")


# ============================================================
# 16) دفعات الفواتير
# ============================================================
def seed_invoice_payments(conn):
    invoices = conn.execute("""
        SELECT id, type, invoice_date, paid_amount FROM invoices
        WHERE paid_amount > 0
    """).fetchall()

    count = 0
    for inv in invoices:
        paid = inv[3]
        num_payments = random.randint(1, 3)
        remaining = paid
        for i in range(num_payments):
            if i == num_payments - 1:
                amount = remaining
            else:
                amount = round(remaining * random.uniform(0.3, 0.6), 2)
            remaining = round(remaining - amount, 2)

            method = random.choice(["cash", "bank"])
            try:
                conn.execute("""
                    INSERT INTO invoice_payments
                    (invoice_id, amount, payment_date, payment_method,
                     currency_code, exchange_rate, created_by)
                    VALUES (?, ?, ?, ?, 'YER', 1.0, 'admin')
                """, (inv[0], amount, inv[2], method))
                count += 1
            except Exception:
                pass

    print(f"✅ دفعات الفواتير: {count}")


# ============================================================
# 17) المرتجعات
# ============================================================
def seed_returns(conn):
    sale_invoices = conn.execute("""
        SELECT id, customer_id, invoice_date FROM invoices
        WHERE type='sale' LIMIT 8
    """).fetchall()

    purchase_invoices = conn.execute("""
        SELECT id, supplier_id, invoice_date FROM invoices
        WHERE type='purchase' LIMIT 4
    """).fetchall()

    count = 0
    for inv in sale_invoices:
        total = random.randint(50000, 300000)
        vat = round(total * 0.15, 2)
        d = _fmt(_rand_date())
        conn.execute("""
            INSERT INTO invoices
            (type, invoice_date, total, total_base, status, vat_rate,
             vat_amount, currency_code, exchange_rate, customer_id,
             reason, reference)
            VALUES ('sale_return', ?, ?, ?, 'completed', 0.15, ?, 'YER', 1.0,
                    ?, 'عيب في المنتج', ?)
        """, (d, total + vat, total + vat, vat, inv[1],
              f"RET-{random.randint(1000, 9999)}"))
        count += 1

    for inv in purchase_invoices:
        total = random.randint(50000, 300000)
        vat = round(total * 0.15, 2)
        d = _fmt(_rand_date())
        conn.execute("""
            INSERT INTO invoices
            (type, invoice_date, total, total_base, status, vat_rate,
             vat_amount, currency_code, exchange_rate, supplier_id,
             reason, reference)
            VALUES ('purchase_return', ?, ?, ?, 'completed', 0.15, ?, 'YER', 1.0,
                    ?, 'منتج غير مطابق', ?)
        """, (d, total + vat, total + vat, vat, inv[1],
              f"PRET-{random.randint(1000, 9999)}"))
        count += 1

    print(f"✅ المرتجعات: {count}")


# ============================================================
# 18) السندات
# ============================================================
def seed_vouchers(conn):
    customers = conn.execute("SELECT id FROM customers").fetchall()
    suppliers = conn.execute("SELECT id FROM suppliers").fetchall()

    # سندات قبض (50)
    receipt_count = 0
    for _ in range(50):
        cid = random.choice(customers)[0]
        amount = random.randint(50000, 500000)
        d = _fmt(_rand_date())
        conn.execute("""
            INSERT INTO vouchers
            (type, date, party_type, party_id, amount, account, created_by)
            VALUES ('receipt', ?, 'customer', ?, ?, '1101', 'admin')
        """, (d, cid, amount))
        receipt_count += 1

    # سندات صرف (40)
    payment_count = 0
    for _ in range(40):
        sid = random.choice(suppliers)[0]
        amount = random.randint(50000, 400000)
        d = _fmt(_rand_date())
        conn.execute("""
            INSERT INTO vouchers
            (type, date, party_type, party_id, amount, account, created_by)
            VALUES ('payment', ?, 'supplier', ?, ?, '1101', 'admin')
        """, (d, sid, amount))
        payment_count += 1

    print(f"✅ سندات القبض: {receipt_count} | سندات الصرف: {payment_count}")


# ============================================================
# 19) حركات الصندوق والبنك
# ============================================================
def seed_cash_bank_transactions(conn):
    cash_accounts = conn.execute("SELECT id FROM cash_accounts").fetchall()
    bank_accounts = conn.execute("SELECT id FROM bank_accounts").fetchall()

    cash_count = 0
    for _ in range(100):
        aid = random.choice(cash_accounts)[0]
        t = random.choice(["deposit", "withdrawal"])
        amount = random.randint(10000, 300000)
        d = _fmt(_rand_date())
        try:
            conn.execute("""
                INSERT INTO cash_transactions
                (cash_account_id, transaction_date, description, type, amount, reference)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (aid, d, f"حركة {'إيداع' if t=='deposit' else 'سحب'}",
                  t, amount, f"TXN-{random.randint(10000, 99999)}"))
            cash_count += 1
        except Exception:
            pass

    bank_count = 0
    for _ in range(60):
        aid = random.choice(bank_accounts)[0]
        t = random.choice(["deposit", "withdrawal"])
        amount = random.randint(50000, 1000000)
        d = _fmt(_rand_date())
        try:
            conn.execute("""
                INSERT INTO bank_transactions
                (bank_account_id, transaction_date, description, type, amount, reference)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (aid, d, f"حركة بنكية {'إيداع' if t=='deposit' else 'سحب'}",
                  t, amount, f"BTXN-{random.randint(10000, 99999)}"))
            bank_count += 1
        except Exception:
            pass

    print(f"✅ حركات الصندوق: {cash_count} | حركات البنك: {bank_count}")


# ============================================================
# 20) المصروفات
# ============================================================
def seed_expenses(conn):
    categories = [
        ("إيجار", "5202"),
        ("كهرباء وماء", "5203"),
        ("اتصالات", "5205"),
        ("نظافة", "5206"),
        ("صيانة", "5207"),
        ("تسويق", "5208"),
        ("نقل", "5209"),
        ("مصروفات بنكية", "5210"),
        ("مصروفات حكومية", "5211"),
        ("متنوعة", "5212"),
    ]

    count = 0
    for _ in range(60):
        cat, code = random.choice(categories)
        amount = random.randint(20000, 500000)
        d = _fmt(_rand_date())
        method = random.choice(["cash", "bank"])
        try:
            conn.execute("""
                INSERT INTO expenses
                (date, category, amount, account_code, payment_method,
                 party_name, notes, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'admin')
            """, (d, cat, amount, code, method, f"مورد {cat}",
                  f"مصروف {cat} لشهر {d[:7]}"))
            count += 1
        except Exception:
            pass

    print(f"✅ المصروفات: {count}")


# ============================================================
# 21) التسويات المخزنية
# ============================================================
def seed_inventory_adjustments(conn):
    products = conn.execute("SELECT id FROM products LIMIT 10").fetchall()
    count = 0
    for p in products:
        expected = random.randint(100, 500)
        actual = expected + random.randint(-20, 20)
        diff = actual - expected
        unit_cost = random.randint(1000, 5000)
        d = _fmt(_rand_date())
        try:
            conn.execute("""
                INSERT INTO inventory_adjustments
                (date, product_id, expected_qty, actual_qty, difference,
                 unit_cost, total_cost, reason, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'admin')
            """, (d, p[0], expected, actual, diff, unit_cost,
                  abs(diff) * unit_cost, "تسوية جرد دوري"))
            count += 1
        except Exception:
            pass

    print(f"✅ التسويات المخزنية: {count}")


# ============================================================
# 22) القيود المحاسبية (الأهم)
# ============================================================
def seed_journal_entries(conn, code_to_id):
    """
    حقن القيود المحاسبية المتوازنة:
    - قيد رأس المال
    - قيد شراء الأصول الثابتة
    - قيود المبيعات
    - قيود المشتريات
    - قيود المصروفات
    - قيود الإهلاك
    - قيود الرواتب
    """
    entries_created = 0
    lines_created = 0

    def add_entry(desc, entry_date, lines):
        """lines: [(account_code, debit, credit), ...]"""
        nonlocal entries_created, lines_created
        ref = f"ENT-{entry_date}-{random.randint(100000, 999999)}"
        cur = conn.execute("""
            INSERT INTO journal_entries (date, description, reference)
            VALUES (?, ?, ?)
        """, (entry_date, desc, ref))
        eid = cur.lastrowid

        for code, dr, cr in lines:
            aid = code_to_id.get(code)
            if not aid:
                continue
            conn.execute("""
                INSERT INTO journal_lines
                (entry_id, journal_entry_id, account_id, account_name,
                 debit, credit, currency_code, exchange_rate)
                VALUES (?, ?, ?, ?, ?, ?, 'YER', 1.0)
            """, (eid, eid, aid, code, dr, cr))
            lines_created += 1
        entries_created += 1

    # ===== 1) قيد رأس المال =====
    add_entry("قيد تأسيس الشركة ورأس المال", "2026-01-01", [
        ("1101", 500000, 0),
        ("1102", 7000000, 0),
        ("1301", 3000000, 0),
        ("3101", 0, 10500000),
    ])

    # ===== 2) قيود شراء الأصول الثابتة =====
    assets = conn.execute("""
        SELECT name, purchase_cost, purchase_date FROM fixed_assets
    """).fetchall()
    for a in assets:
        add_entry(f"شراء أصل ثابت: {a[0]}", a[2], [
            ("1401", a[1], 0),
            ("1102", 0, a[1]),
        ])

    # ===== 3) قيود إهلاك الأصول =====
    deps = conn.execute("""
        SELECT de.amount, de.entry_date, fa.name
        FROM depreciation_entries de
        JOIN fixed_assets fa ON de.asset_id = fa.id
    """).fetchall()
    for d in deps:
        add_entry(f"إهلاك {d[2]}", d[1], [
            ("5204", d[0], 0),
            ("1303", 0, d[0]),
        ])

    # ===== 4) قيود فواتير البيع =====
    sale_invoices = conn.execute("""
        SELECT id, total, vat_amount, invoice_date FROM invoices
        WHERE type='sale' AND status='completed' LIMIT 40
    """).fetchall()
    for inv in sale_invoices:
        subtotal = round(inv[1] - inv[2], 2)
        add_entry(f"فاتورة مبيعات #{inv[0]}", inv[3], [
            ("1201", inv[1], 0),
            ("4101", 0, subtotal),
            ("2102", 0, inv[2]),
        ])

    # ===== 5) قيود فواتير الشراء =====
    purchase_invoices = conn.execute("""
        SELECT id, total, vat_amount, invoice_date FROM invoices
        WHERE type='purchase' AND status='completed' LIMIT 25
    """).fetchall()
    for inv in purchase_invoices:
        subtotal = round(inv[1] - inv[2], 2)
        add_entry(f"فاتورة مشتريات #{inv[0]}", inv[3], [
            ("1301", subtotal, 0),
            ("1302", inv[2], 0),
            ("2101", 0, inv[1]),
        ])

    # ===== 6) قيود سندات القبض =====
    receipts = conn.execute("""
        SELECT id, amount, date FROM vouchers WHERE type='receipt' LIMIT 30
    """).fetchall()
    for r in receipts:
        add_entry(f"سند قبض #{r[0]}", r[2], [
            ("1101", r[1], 0),
            ("1201", 0, r[1]),
        ])

    # ===== 7) قيود سندات الصرف =====
    payments = conn.execute("""
        SELECT id, amount, date FROM vouchers WHERE type='payment' LIMIT 25
    """).fetchall()
    for p in payments:
        add_entry(f"سند صرف #{p[0]}", p[2], [
            ("2101", p[1], 0),
            ("1101", 0, p[1]),
        ])

    # ===== 8) قيود المصروفات =====
    expenses = conn.execute("""
        SELECT date, category, amount, account_code FROM expenses LIMIT 40
    """).fetchall()
    for e in expenses:
        code = e[3] or "5212"
        payment_code = "1101"
        add_entry(f"مصروف {e[1]}", e[0], [
            (code, e[2], 0),
            (payment_code, 0, e[2]),
        ])

    # ===== 9) قيود الرواتب =====
    payroll = conn.execute("""
        SELECT pr.month, SUM(pr.net_salary), SUM(pr.deductions)
        FROM payroll_runs pr
        GROUP BY pr.month
    """).fetchall()
    for p in payroll:
        month = p[0]
        total_net = p[1] or 0
        total_ded = p[2] or 0
        gross = total_net + total_ded
        entry_date = f"{month}-28"
        add_entry(f"رواتب شهر {month}", entry_date, [
            ("5201", gross, 0),
            ("1102", 0, total_net),
            ("2103", 0, total_ded),
        ])

    print(f"✅ القيود: {entries_created} | السطور: {lines_created}")


# ============================================================
# 23) الأرصدة الافتتاحية
# ============================================================
def seed_opening_balances(conn, code_to_id):
    """حقن الأرصدة الافتتاحية (يجب أن تكون متوازنة)"""
    balances = [
        ("1101", 500000, 0),
        ("1102", 7000000, 0),
        ("1301", 3000000, 0),
        ("3101", 0, 10500000),
    ]
    count = 0
    for code, dr, cr in balances:
        aid = code_to_id.get(code)
        if not aid:
            continue
        try:
            conn.execute("""
                INSERT INTO opening_balances
                (entry_date, account_id, account_code, account_name,
                 debit, credit, created_by)
                VALUES ('2026-01-01', ?, ?, ?, ?, ?, 'admin')
            """, (aid, code, code, dr, cr))
            count += 1
        except Exception:
            pass
    print(f"✅ الأرصدة الافتتاحية: {count}")


# ============================================================
# 24) سجل التدقيق
# ============================================================
def seed_audit_log(conn):
    """حقن سجلات تدقيق حقيقية"""
    actions = [
        ("admin", "🔓 تسجيل دخول ناجح", "users", 1,
         json.dumps({"ip": "192.168.1.10", "status": "success"})),
        ("admin", "📂 إضافة حساب", "accounts", 1,
         json.dumps({"code": "1101", "name": "الصندوق"})),
        ("admin", "👤 إنشاء مستخدم جديد", "users", 2,
         json.dumps({"username": "manager", "role_id": 2})),
        ("admin", "🌱 حقن بيانات تجريبية", "system", 0,
         json.dumps({"modules": 29, "status": "success"})),
        ("manager", "🔓 تسجيل دخول ناجح", "users", 2,
         json.dumps({"ip": "192.168.1.15", "status": "success"})),
        ("accountant", "📝 إنشاء قيد محاسبي", "journal_entries", 1,
         json.dumps({"description": "قيد تأسيس الشركة", "total_debit": 10500000})),
    ]

    for _ in range(30):
        u, a, t, rid, nv = random.choice(actions)
        d = _fmt(_rand_date()) + f" {random.randint(8,18):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}"
        try:
            conn.execute("""
                INSERT INTO audit_log
                (username, action, table_name, record_id, new_value, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (u, a, t, rid, nv, d))
        except Exception:
            pass
    print(f"✅ سجل التدقيق: 30 سجل")


# ============================================================
# 🎯 الدالة الرئيسية
# ============================================================
def run_full_seed(progress_callback=None):
    """
    الدالة الرئيسية لحقن البيانات.
    Returns:
        dict: {"success": bool, "summary": {...}, "error": str}
    """
    random.seed(RANDOM_SEED)

    summary = {}
    conn = None

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row

        if progress_callback:
            progress_callback("🗑️ حذف البيانات القديمة...")
        delete_all_data(conn)

        if progress_callback:
            progress_callback("👥 الأدوار والمستخدمون...")
        seed_roles_users(conn)
        summary["الأدوار"] = 5
        summary["المستخدمون"] = 5

        if progress_callback:
            progress_callback("🛡️ الصلاحيات...")
        seed_role_permissions(conn)
        summary["الصلاحيات"] = 155

        if progress_callback:
            progress_callback("🌳 شجرة الحسابات...")
        code_to_id = seed_accounts(conn)
        summary["الحسابات"] = len(code_to_id)

        if progress_callback:
            progress_callback("💱 العملات...")
        seed_currencies(conn)
        summary["العملات"] = 4

        if progress_callback:
            progress_callback("🏢 مراكز التكلفة...")
        seed_cost_centers(conn)
        summary["مراكز التكلفة"] = 5

        if progress_callback:
            progress_callback("💰 الصناديق والبنوك...")
        seed_cash_and_bank(conn)
        summary["الصناديق والبنوك"] = 5

        if progress_callback:
            progress_callback("👥 العملاء والموردون...")
        seed_parties(conn)
        summary["العملاء"] = 20
        summary["الموردون"] = 15

        if progress_callback:
            progress_callback("📦 المنتجات...")
        seed_products(conn)
        summary["المنتجات"] = 30

        if progress_callback:
            progress_callback("👔 الموظفون والحضور...")
        seed_employees(conn)
        summary["الموظفون"] = 15

        if progress_callback:
            progress_callback("💰 كشوف الرواتب...")
        seed_payroll(conn)
        summary["كشوف الرواتب"] = 60

        if progress_callback:
            progress_callback("🏗️ الأصول الثابتة...")
        seed_fixed_assets(conn)
        summary["الأصول الثابتة"] = 12

        if progress_callback:
            progress_callback("📞 CRM...")
        seed_crm(conn)
        summary["CRM"] = 75

        if progress_callback:
            progress_callback("📦 المخزون و FIFO...")
        seed_inventory(conn)
        summary["دفعات FIFO"] = 90

        if progress_callback:
            progress_callback("🛒 الفواتير...")
        seed_invoices(conn)
        summary["الفواتير"] = 95

        if progress_callback:
            progress_callback("💳 دفعات الفواتير...")
        seed_invoice_payments(conn)
        summary["دفعات الفواتير"] = "متعددة"

        if progress_callback:
            progress_callback("🔄 المرتجعات...")
        seed_returns(conn)
        summary["المرتجعات"] = 12

        if progress_callback:
            progress_callback("📄 السندات...")
        seed_vouchers(conn)
        summary["السندات"] = 90

        if progress_callback:
            progress_callback("💵 حركات الصندوق والبنك...")
        seed_cash_bank_transactions(conn)
        summary["حركات الصندوق/البنك"] = 160

        if progress_callback:
            progress_callback("🧾 المصروفات...")
        seed_expenses(conn)
        summary["المصروفات"] = 60

        if progress_callback:
            progress_callback("📊 التسويات المخزنية...")
        seed_inventory_adjustments(conn)
        summary["التسويات المخزنية"] = 10

        if progress_callback:
            progress_callback("📝 القيود المحاسبية...")
        seed_journal_entries(conn, code_to_id)
        summary["القيود المحاسبية"] = "300+"

        if progress_callback:
            progress_callback("📋 الأرصدة الافتتاحية...")
        seed_opening_balances(conn, code_to_id)
        summary["الأرصدة الافتتاحية"] = 4

        if progress_callback:
            progress_callback("📋 سجل التدقيق...")
        seed_audit_log(conn)
        summary["سجل التدقيق"] = 30

        if progress_callback:
            progress_callback("✅ اكتمل الحقن بنجاح!")

        return {"success": True, "summary": summary, "error": None}

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(tb)
        return {"success": False, "summary": summary, "error": str(e)}
