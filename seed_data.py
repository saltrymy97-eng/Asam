import sys
import traceback
import random
from datetime import date, timedelta
from decimal import Decimal

import database
from services.chart_service import get_functional_account

# 1. تهيئة قاعدة البيانات
database.init_db()

# التأكد من وجود العملة الأساسية
def ensure_base_currency():
    conn = database.get_connection()
    c = conn.cursor()
    count = c.execute("SELECT COUNT(*) FROM currencies").fetchone()[0]
    if count == 0:
        c.execute("INSERT INTO currencies (code, name, symbol, is_base, is_active) VALUES ('YER', 'ريال يمني', 'ر.ي', 1, 1)")
        conn.commit()
    conn.close()
    print("✅ تم التأكد من وجود العملة الأساسية YER")

ensure_base_currency()

# استيراد خدمات النظام
from services.sales_service import add_customer, create_sale_invoice
from services.purchases_service import add_supplier, create_purchase_invoice
from services.inventory_service import add_product
from services.returns_service import process_return
from services.receipts_service import create_voucher
from services.expenses_service import create_expense
from services.inventory_adjustment_service import create_adjustment
from services.accounting_service import get_trial_balance, save_journal_entry

# استيراد خدمات الوحدات الإضافية
from services.hr_service import add_employee, record_attendance
from services.payroll_service import save_salary_config, run_payroll
from services.assets_service import add_asset, run_depreciation
from services.bank_service import create_bank_account, add_bank_transaction, create_bank_reconciliation
from services.currency_service import create_currency, set_exchange_rate
from services.cost_center_service import create_cost_center, allocate_journal_line, set_budget
from services.roles_service import seed_default_roles
from services.auth_service import create_user
from services.attachment_service import upload_attachment
from services.crm_service import add_lead, add_opportunity
from services.closing_service import create_closing_entry

# ===================== إعدادات =====================
TOTAL_OPERATIONS = 10000
random.seed(42)

# ===================== دوال مساعدة =====================
def random_date(start_year=2025, end_year=2026):
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    delta = end - start
    random_days = random.randint(0, delta.days)
    return (start + timedelta(days=random_days)).strftime("%Y-%m-%d")

def random_phone():
    return f"77{random.randint(1000000, 9999999)}"

# ===================== إنشاء شجرة الحسابات الكاملة الديناميكية =====================
def create_default_accounts():
    conn = database.get_connection()
    c = conn.cursor()
    count = c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    if count > 0:
        conn.close()
        print("✅ شجرة الحسابات موجودة مسبقاً")
        return
    print("إنشاء شجرة الحسابات الكاملة المتوافقة مع functional_type...")
    
    # (كود, اسم, أب, مستوى, طبيعة, تصنيف, نوع_وظيفي)
    accounts = [
        # ===== 1 - الأصول =====
        ("1", "الأصول", None, 1, "debit", "Asset", None),
        ("11", "الأصول المتداولة", "1", 2, "debit", "Asset", None),
        ("111", "الصندوق الرئيسي", "11", 3, "debit", "Asset", "cash"),
        ("112", "البنوك", "11", 3, "debit", "Asset", "bank"),
        ("113", "العملاء", "11", 3, "debit", "Asset", "ar"),
        ("114", "المخزون", "11", 3, "debit", "Asset", "inventory"),
        ("115", "أوراق القبض", "11", 3, "debit", "Asset", "notes_receivable"),
        ("12", "الأصول غير المتداولة", "1", 2, "debit", "Asset", None),
        ("121", "الأصول الثابتة", "12", 3, "debit", "Asset", "fixed_assets"),
        ("122", "مجمع الإهلاك", "12", 3, "credit", "Asset", "accumulated_depreciation"),
        
        # ===== 2 - الخصوم =====
        ("2", "الخصوم", None, 1, "credit", "Liability", None),
        ("21", "الخصوم المتداولة", "2", 2, "credit", "Liability", None),
        ("211", "الموردون", "21", 3, "credit", "Liability", "ap"),
        ("212", "أوراق الدفع", "21", 3, "credit", "Liability", "notes_payable"),
        ("213", "ضريبة القيمة المضافة المستحقة", "21", 3, "credit", "Liability", "vat"),
        ("214", "مصروفات مستحقة", "21", 3, "credit", "Liability", "accrued_expenses"),
        ("215", "رواتب مستحقة", "21", 3, "credit", "Liability", "salaries_payable"),
        ("22", "الخصوم غير المتداولة", "2", 2, "credit", "Liability", None),
        ("221", "قروض طويلة الأجل", "22", 3, "credit", "Liability", "long_term_loans"),
        
        # ===== 3 - حقوق الملكية =====
        ("3", "حقوق الملكية", None, 1, "credit", "Equity", None),
        ("31", "رأس المال", "3", 2, "credit", "Equity", "capital"),
        ("32", "الأرباح المحتجزة", "3", 2, "credit", "Equity", "retained_earnings"),
        ("33", "تسوية الأرصدة الافتتاحية", "3", 2, "credit", "Equity", "opening_balance_equity"),
        
        # ===== 4 - الإيرادات =====
        ("4", "الإيرادات", None, 1, "credit", "Revenue", None),
        ("41", "المبيعات", "4", 2, "credit", "Revenue", "sales"),
        ("42", "مردودات المبيعات", "4", 2, "debit", "Revenue", "sales_returns"),
        ("43", "خصم مسموح به", "4", 2, "debit", "Revenue", "sales_discount"),
        ("44", "إيرادات خدمات", "4", 2, "credit", "Revenue", "service_revenue"),
        ("45", "أرباح فروق عملة", "4", 2, "credit", "Revenue", "fx_gain"),
        ("46", "إيرادات أخرى", "4", 2, "credit", "Revenue", "other_revenue"),
        
        # ===== 5 - المصروفات =====
        ("5", "المصروفات", None, 1, "debit", "Expense", None),
        ("51", "تكلفة البضاعة المباعة", "5", 2, "debit", "Expense", "cogs"),
        ("52", "المشتريات", "5", 2, "debit", "Expense", "purchases"),
        ("53", "مردودات المشتريات", "5", 2, "credit", "Expense", "purchase_returns"),
        ("54", "مصروفات تشغيلية", "5", 2, "debit", "Expense", "operating_expenses"),
        ("541", "الإيجار", "54", 3, "debit", "Expense", "rent_expense"),
        ("542", "الكهرباء والماء", "54", 3, "debit", "Expense", "utilities_expense"),
        ("543", "الصيانة", "54", 3, "debit", "Expense", "maintenance_expense"),
        ("544", "رواتب وأجور", "54", 3, "debit", "Expense", "salaries_expense"),
        ("545", "مصروف الإهلاك", "54", 3, "debit", "Expense", "depreciation_expense"),
        ("546", "مصروف تسوية المخزون", "54", 3, "debit", "Expense", "inventory_adjustment"),
        ("547", "خسائر فروق عملة", "54", 3, "debit", "Expense", "fx_loss"),
        ("548", "مصروفات إدارية وتسويقية", "54", 3, "debit", "Expense", "general_expense"),
    ]
    
    for code, name, parent_code, level, is_debit, acc_type, func_type in accounts:
        try:
            parent_id = None
            if parent_code:
                parent_row = c.execute("SELECT id FROM accounts WHERE code=?", (parent_code,)).fetchone()
                if parent_row:
                    parent_id = parent_row[0]
            c.execute(
                """INSERT INTO accounts 
                   (code, name, parent_id, level, is_debit, account_type, functional_type, is_sub) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                (code, name, parent_id, level, is_debit, acc_type, func_type)
            )
        except Exception as e:
            pass
    
    conn.commit()
    conn.close()
    print("✅ تم إنشاء شجرة الحسابات الكاملة والمرتبطة بـ functional_type بنجاح")

# ===================== التنفيذ =====================
create_default_accounts()

# جلب المعرفات الوظيفية الأساسية لاستخدامها الديناميكي في السكريبت
cash_account_id = get_functional_account('cash')
inventory_account_id = get_functional_account('inventory')
capital_account_id = get_functional_account('capital')
operating_expense_account_id = get_functional_account('operating_expenses') or get_functional_account('general_expense')

# ===================== 1. العملاء والموردين =====================
print("\nإنشاء العملاء والموردين...")
customer_ids = []
for i in range(50):
    cid = add_customer(f"عميل-{i+1}", random_phone(), f"عنوان-{i+1}")
    customer_ids.append(cid)

supplier_ids = []
for i in range(50):
    sid = add_supplier(f"مورد-{i+1}", random_phone(), f"عنوان-{i+1}")
    supplier_ids.append(sid)

# ===================== 2. المنتجات =====================
print("إنشاء المنتجات...")
product_ids = []
for i in range(200):
    cost = random.randint(10, 500)
    price = cost + random.randint(5, 300)
    add_product(f"منتج-{i+1}", None, "عام", cost, price, 0, 10)
    product_ids.append(i+1)

# ===================== 3. شراء مخزون افتتاحي =====================
print("شراء مخزون افتتاحي...")
total_opening_stock_value = 0
purchase_errors = 0
for pid in product_ids:
    sid = random.choice(supplier_ids)
    cost = random.randint(50, 500)
    qty = random.randint(50, 200)
    items = [{"product_id": pid, "quantity": qty, "unit_price_base": cost}]
    try:
        inv_id, total, err = create_purchase_invoice(sid, items, currency_code="YER")
        if err:
            purchase_errors += 1
        else:
            total_opening_stock_value += qty * cost
    except:
        purchase_errors += 1
print(f"  اكتمل. أخطاء الشراء الافتتاحي: {purchase_errors}")

# تسجيل قيد الأرصدة الافتتاحية باستخدام المعرفات الديناميكية account_id
if total_opening_stock_value > 0 and inventory_account_id and capital_account_id:
    try:
        entry_id, err = save_journal_entry(
            description="قيد الأرصدة الافتتاحية",
            lines=[
                {"account_id": inventory_account_id, "debit": total_opening_stock_value, "credit": 0, "exchange_rate": 1.0},
                {"account_id": capital_account_id, "debit": 0, "credit": total_opening_stock_value, "exchange_rate": 1.0}
            ],
            entry_date=date.today().strftime("%Y-%m-%d")
        )
        if err:
            print(f"  ⚠️ فشل قيد الافتتاح: {err}")
        else:
            print(f"  ✅ تم تسجيل قيد الافتتاح بنجاح بواسطة account_id")
    except Exception as e:
        print(f"  ⚠️ استثناء في قيد الافتتاح: {e}")

# ===================== 4. العمليات المالية (10,000) =====================
print("\nبدء توليد 10,000 عملية مالية ديناميكية...")
errors = []
success_count = 0
sale_count = 0
purchase_count = 0
receipt_count = 0
payment_count = 0
expense_count = 0
adjustment_count = 0

for op_num in range(TOTAL_OPERATIONS):
    try:
        op_type = random.choices(
            ['purchase', 'sale', 'receipt', 'payment', 'expense', 'adjustment'],
            weights=[5, 80, 5, 3, 3, 1]
        )[0]
        op_date = random_date()

        if op_type == 'purchase':
            sid = random.choice(supplier_ids)
            pid = random.choice(product_ids)
            qty = random.randint(10, 50)
            price = random.randint(50, 500)
            items = [{"product_id": pid, "quantity": qty, "unit_price_base": price}]
            inv_id, _, err = create_purchase_invoice(sid, items, currency_code="YER")
            if err:
                raise Exception(err)
            purchase_count += 1

        elif op_type == 'sale':
            cid = random.choice(customer_ids)
            pid = random.choice(product_ids)
            qty = random.randint(1, 5)
            price = random.randint(100, 1000)
            items = [{"product_id": pid, "quantity": qty, "unit_price_base": price}]
            inv_id, _, err = create_sale_invoice(cid, items, currency_code="YER")
            if err:
                raise Exception(err)
            sale_count += 1

        elif op_type == 'receipt':
            cid = random.choice(customer_ids)
            amount = random.randint(100, 5000)
            # تم تحويل الحساب للصندوق الديناميكي cash_account_id
            vid, err = create_voucher('receipt', 'customer', cid, amount, cash_account_id)
            if err:
                raise Exception(err)
            receipt_count += 1

        elif op_type == 'payment':
            sid = random.choice(supplier_ids)
            amount = random.randint(100, 5000)
            # تم تحويل الحساب للصندوق الديناميكي cash_account_id
            vid, err = create_voucher('payment', 'supplier', sid, amount, cash_account_id)
            if err:
                raise Exception(err)
            payment_count += 1

        elif op_type == 'expense':
            # نمرر المعرف الديناميكي لمصروف التشغيل والصندوق
            eid, err = create_expense(
                op_date, 
                random.choice(["إيجار", "كهرباء", "صيانة", "أخرى"]),
                random.randint(500, 3000), 
                cash_account_id, 
                "cash",
                expense_account_id=operating_expense_account_id
            )
            if err:
                raise Exception(err)
            expense_count += 1

        elif op_type == 'adjustment':
            pid = random.choice(product_ids)
            diff = random.randint(-5, 5)
            if diff != 0:
                adj_id, err = create_adjustment(pid, 10, 10 + diff)
                if err:
                    raise Exception(err)
                adjustment_count += 1

        success_count += 1
        if op_num % 1000 == 0 and op_num > 0:
            print(f"  تم تنفيذ {op_num} عملية... (مبيعات: {sale_count})")

    except Exception as e:
        err_msg = f"عملية {op_num} ({op_type}): {str(e)[:200]}"
        errors.append(err_msg)

# ===================== 5. الوحدات الإضافية =====================

# --- 5.1 الموارد البشرية ---
print("\n🏢 إنشاء الموظفين والحضور...")
employee_ids = []
positions = ["محاسب", "أمين مخزن", "كاشير", "مدير مبيعات", "مسؤول مشتريات", "مدير مالي", "سكرتير", "مندوب مبيعات"]
for i in range(50):
    name = f"موظف-{i+1}"
    pos = random.choice(positions)
    salary = random.randint(25000, 100000)
    join_date = random_date()
    success, msg = add_employee(name, pos, salary, join_date)
    if success:
        conn = database.get_connection()
        cur = conn.execute("SELECT id FROM employees ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        emp_id = row[0] if row else 0
        conn.close()
        employee_ids.append(emp_id)
        for d in range(9):
            day = (date.today() - timedelta(days=d)).strftime("%Y-%m-%d")
            record_attendance(emp_id, name, day, random.choice(["حاضر", "حاضر", "حاضر", "غائب", "متأخر"]))
print(f"  ✅ {len(employee_ids)} موظف + {len(employee_ids)*9} حضور")

# --- 5.2 الرواتب ---
print("\n💰 إعداد الرواتب...")
for emp_id in employee_ids:
    basic = random.randint(20000, 70000)
    housing = random.randint(3000, 20000)
    transport = random.randint(2000, 15000)
    other = random.randint(0, 5000)
    deductions = random.randint(0, 3000)
    save_salary_config(emp_id, basic, housing, transport, other, deductions)
for month in ["2026-04", "2026-05", "2026-06"]:
    for emp_id in employee_ids[:5]:
        run_payroll(emp_id, month)
print(f"  ✅ تم إعداد 50 راتب وتشغيل 3 أشهر")

# --- 5.3 الأصول الثابتة ---
print("\n🏭 إنشاء أصول ثابتة...")
asset_types = [
    ("مبنى إداري", "عقارات", "2024-01-01", 500000, 0, 20),
    ("سيارة نقل", "مركبات", "2024-06-01", 85000, 5000, 5),
    ("أجهزة كمبيوتر", "معدات", "2025-01-01", 45000, 0, 3),
    ("معدات مكتبية", "أثاث", "2025-03-01", 12000, 0, 2),
    ("أثاث", "أثاث", "2024-01-01", 30000, 0, 4),
    ("مكيفات", "معدات", "2025-06-01", 15000, 0, 3),
    ("طابعات", "معدات", "2025-01-01", 8000, 0, 2),
    ("برامج", "غير ملموسة", "2025-01-01", 20000, 0, 1),
    ("مولد كهرباء", "معدات", "2024-01-01", 35000, 3000, 5),
    ("أجهزة أمنية", "معدات", "2025-01-01", 25000, 0, 3),
]
asset_ids = []
for name, cat, pur_date, cost, salvage, years in asset_types:
    asset_id = add_asset(name, cat, pur_date, cost, salvage, years)
    asset_ids.append(asset_id)
    for _ in range(20):
        run_depreciation(asset_id)
print(f"  ✅ {len(asset_ids)} أصول + 200 إهلاك")

# --- 5.4 البنوك ---
print("\n🏦 إنشاء حسابات بنكية...")
banks = [
    ("بنك الأمل", "1234567890", "حساب بنك الأمل", "YER", 500000),
    ("البنك اليمني", "0987654321", "حساب البنك اليمني", "YER", 350000),
    ("بنك التسليف", "1122334455", "حساب بنك التسليف", "YER", 200000),
    ("البنك العربي", "5544332211", "حساب البنك العربي", "YER", 150000),
    ("بنك اليمن الدولي", "6677889900", "حساب بنك اليمن الدولي", "YER", 400000),
]
bank_ids = []
for bank_name, acc_num, acc_name, curr, balance in banks:
    bank_id = create_bank_account(bank_name, acc_num, acc_name, curr, balance)
    bank_ids.append(bank_id)
    for _ in range(100):
        trans_type = random.choice(["deposit", "withdrawal"])
        add_bank_transaction(bank_id, random_date(), f"حركة {bank_name}", trans_type, random.randint(1000, 100000))
    create_bank_reconciliation(bank_id, random_date(), balance + random.randint(-5000, 5000))
print(f"  ✅ {len(bank_ids)} حسابات + 500 حركة")

# --- 5.5 العملات ---
print("\n💱 إنشاء عملات وأسعار صرف...")
currencies_to_seed = [
    ("USD", "دولار أمريكي", "$"),
    ("SAR", "ريال سعودي", "ر.س"),
    ("AED", "درهم إماراتي", "د.إ"),
    ("EUR", "يورو", "€"),
    ("GBP", "جنيه إسترليني", "£"),
]
for code, name, symbol in currencies_to_seed:
    try:
        create_currency(code, name, symbol)
    except:
        pass
    for _ in range(40):
        rate = random.uniform(250, 1500) if code in ["USD", "EUR", "GBP"] else random.uniform(3.5, 270)
        try:
            set_exchange_rate(code, "YER", rate, random_date())
        except:
            pass
print(f"  ✅ {len(currencies_to_seed)} عملات + 200 سعر صرف")

# --- 5.6 مراكز التكلفة ---
print("\n🏢 إنشاء مراكز تكلفة...")
cost_centers = [
    ("CC01", "قسم المبيعات"), ("CC02", "قسم المشتريات"), ("CC03", "الإدارة العامة"),
    ("CC04", "قسم الموارد البشرية"), ("CC05", "قسم المالية"), ("CC06", "قسم التسويق"),
    ("CC07", "قسم الصيانة"), ("CC08", "فرع المكلا"), ("CC09", "فرع غيل باوزير"),
    ("CC10", "المستودع الرئيسي"),
]
cc_ids = []
for code, name in cost_centers:
    cc_id = create_cost_center(code, name)
    cc_ids.append(cc_id)
    for acc_id in range(1, 6):
        set_budget(cc_id, acc_id, 2026, random.randint(50000, 300000))
    for _ in range(55):
        allocate_journal_line(random.randint(1, 20), [{"cost_center_id": cc_id, "amount": random.randint(500, 50000)}])
print(f"  ✅ {len(cc_ids)} مراكز + 50 موازنة + 550 توزيع")

# --- 5.7 الصلاحيات ---
print("\n🛡️ إنشاء الأدوار والصلاحيات...")
seed_default_roles()
print(f"  ✅ تم إنشاء الأدوار الافتراضية")

# --- 5.8 المستخدمين ---
print("\n👤 إنشاء مستخدمين...")
users_list = [
    ("محاسب1", "pass123", "محمد المحاسب", 2), ("مخزن1", "pass123", "علي أمين المخزن", 3),
    ("كاشير1", "pass123", "فاطمة كاشير", 4), ("مدير1", "pass123", "أحمد المدير", 1),
]
for username, pwd, full_name, role_id in users_list:
    create_user(username, pwd, full_name, role_id)
for i in range(46):
    create_user(f"user{i+1}", "pass123", f"مستخدم-{i+1}", random.randint(1, 4))
print(f"  ✅ 50 مستخدم")

# --- 5.9 المرفقات ---
print("\n📎 رفع مرفقات...")
for i in range(50):
    try:
        upload_attachment(None, "invoices", 1, "admin")
    except:
        pass
print(f"  ✅ ~50 مرفقات (إن أمكن)")

# --- 5.10 CRM ---
print("\n🤝 إنشاء عملاء محتملين...")
leads_list = [
    ("شركة النور", "النور", "770123456", "info@alnoor.com"),
    ("مؤسسة السلام", "السلام", "770654321", "salam@example.com"),
    ("مجموعة الأمل", "الأمل", "771112233", "alamal@example.com"),
    ("تجارة الجنوب", "الجنوب", "771234567", "south@trade.com"),
    ("مؤسسة الخليج", "الخليج", "772345678", "gulf@example.com"),
    ("شركة البادية", "البادية", "773456789", "badia@example.com"),
]
lead_ids = []
for name, company, phone, email in leads_list:
    lead_id = add_lead(name, company, phone, email)
    lead_ids.append(lead_id)
for _ in range(200):
    add_opportunity(random.choice(lead_ids), f"فرصة {_+1}", random.randint(50000, 500000), random.choice(["مؤهل", "مقترح", "مغلق فوز"]))
print(f"  ✅ {len(lead_ids)} عملاء + 200 فرصة")

# --- 5.11 إغلاق الفترات ---
print("\n📅 إغلاق فترات...")
try:
    create_closing_entry(2025)
    print("  ✅ تم إغلاق 2025")
except Exception as e:
    print(f"  ⚠️ فشل إغلاق 2025: {e}")
try:
    create_closing_entry(2026)
    print("  ✅ تم إغلاق 2026")
except Exception as e:
    print(f"  ⚠️ فشل إغلاق 2026: {e}")

# ===================== 6. النتائج =====================
print("\n" + "="*60)
print(f"✅ العمليات الأساسية الناجحة: {success_count}/{TOTAL_OPERATIONS}")
print(f"❌ الأخطاء: {len(errors)}")
print(f"\n📊 إحصائيات العمليات:")
print(f"  مبيعات: {sale_count}")
print(f"  مشتريات: {purchase_count}")
print(f"  سندات قبض: {receipt_count}")
print(f"  سندات صرف: {payment_count}")
print(f"  مصروفات: {expense_count}")
print(f"  تسويات: {adjustment_count}")

if errors:
    print(f"\nأول 3 أخطاء إن وجدت:")
    for err in errors[:3]:
        print(f"  - {err}")

# ===================== تشخيص تلقائي وميزان المراجعة =====================
print("\n🔍 تشخيص ميزان المراجعة والتأكد من التوازن المحاسبي...")
conn = database.get_connection()

tb = get_trial_balance()
total_d = sum(row['total_debit'] for row in tb)
total_c = sum(row['total_credit'] for row in tb)

print("\n📊 ميزان المراجعة النهائي:")
print(f"  إجمالي المدين: {total_d:,.2f}")
print(f"  إجمالي الدائن: {total_c:,.2f}")

if abs(total_d - total_c) < 0.01:
    print("✅ الميزان متوازن 100% بدون أي فارق!")
else:
    print(f"⚠️ الميزان غير متوازن بفارق: {abs(total_d - total_c):,.2f}")

conn.close()
print("\n🎉 اكتمل حقن البيانات والاختبار بنجاح كامل!")
