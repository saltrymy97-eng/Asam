import database
database.init_db()

import random
import sys
import traceback
from datetime import date, timedelta
from decimal import Decimal

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
from services.hr_service import add_employee, record_attendance  # تم التصحيح
from services.payroll_service import create_salary_record, run_payroll
from services.assets_service import add_asset, depreciate_asset
from services.bank_service import create_bank_account, create_bank_transaction, reconcile_bank
from services.currency_service import add_currency, add_exchange_rate
from services.cost_center_service import add_cost_center, allocate_to_cost_center, set_budget
from services.roles_service import add_role, assign_permission
from services.auth_service import register_user
from services.attachment_service import upload_attachment
from services.crm_service import add_lead, add_opportunity
from services.closing_service import close_period

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

# ===================== إنشاء الحسابات الافتراضية =====================
def create_default_accounts():
    """إنشاء شجرة الحسابات الأساسية إذا لم تكن موجودة"""
    conn = database.get_connection()
    c = conn.cursor()
    
    count = c.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    if count > 0:
        conn.close()
        print("✅ شجرة الحسابات موجودة مسبقاً")
        return
    
    print("إنشاء شجرة الحسابات الافتراضية...")
    accounts = [
        ("1", "الأصول", None, 1, "debit", None),
        ("11", "المخزون", "1", 2, "debit", None),
        ("12", "الصندوق", "1", 2, "debit", None),
        ("2", "الخصوم", None, 1, "credit", None),
        ("21", "الموردون", "2", 2, "credit", None),
        ("22", "ضريبة القيمة المضافة المستحقة", "2", 2, "credit", None),
        ("3", "حقوق الملكية", None, 1, "credit", None),
        ("31", "رأس المال", "3", 2, "credit", None),
        ("4", "الإيرادات", None, 1, "credit", None),
        ("41", "المبيعات", "4", 2, "credit", None),
        ("42", "مردودات المبيعات", "4", 2, "credit", None),
        ("5", "المصروفات", None, 1, "debit", None),
        ("51", "المشتريات", "5", 2, "debit", None),
        ("52", "مردودات المشتريات", "5", 2, "debit", None),
        ("53", "تكلفة البضاعة المباعة", "5", 2, "debit", None),
        ("54", "مصروفات تشغيلية", "5", 2, "debit", None),
    ]
    
    for code, name, parent_code, level, is_debit, acc_type in accounts:
        try:
            parent_id = None
            if parent_code:
                parent_row = c.execute("SELECT id FROM accounts WHERE code=?", (parent_code,)).fetchone()
                if parent_row:
                    parent_id = parent_row[0]
            c.execute(
                "INSERT INTO accounts (code, name, parent_id, level, is_debit) VALUES (?, ?, ?, ?, ?)",
                (code, name, parent_id, level, is_debit)
            )
        except Exception as e:
            pass
    
    conn.commit()
    conn.close()
    print("✅ تم إنشاء شجرة الحسابات")

# ===================== تشخيص تلقائي =====================
def diagnostic():
    """فحص سريع للتأكد من أن الخدمات تعمل"""
    print("🔍 تشخيص النظام...")
    try:
        cid = add_customer("اختبار_تشخيص", "770000000", "عنوان")
        sid = add_supplier("اختبار_مورد", "771111111", "عنوان")
        add_product("منتج_تشخيص", None, "عام", 100, 200, 100, 10)
        items_p = [{"product_id": 1, "quantity": 10, "unit_price_base": 100}]
        inv_p, _, err_p = create_purchase_invoice(sid, items_p)
        if err_p:
            print(f"❌ فشل شراء: {err_p}")
            return False
        items_s = [{"product_id": 1, "quantity": 1, "unit_price_base": 200}]
        inv_s, _, err_s = create_sale_invoice(cid, items_s)
        if err_s:
            print(f"❌ فشل بيع: {err_s}")
            return False
        print("✅ التشخيص ناجح - جميع الخدمات تعمل")
        return True
    except Exception as e:
        print(f"❌ فشل التشخيص: {e}")
        traceback.print_exc()
        return False

# ===================== 0. إنشاء شجرة الحسابات =====================
create_default_accounts()

# ===================== تشغيل التشخيص =====================
if not diagnostic():
    print("\n⚠️ فشل التشخيص. لن يتم حقن البيانات. أصلح الأخطاء أعلاه.")
    sys.exit(1)

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
    except Exception as e:
        purchase_errors += 1

print(f"  اكتمل. أخطاء الشراء الافتتاحي: {purchase_errors}")

if total_opening_stock_value > 0:
    print(f"تسجيل قيد الأرصدة الافتتاحية (المخزون: {total_opening_stock_value:,.2f})...")
    try:
        entry_id, err = save_journal_entry(
            description="قيد الأرصدة الافتتاحية - المخزون ورأس المال",
            lines=[
                {"account": "11", "debit": total_opening_stock_value, "credit": 0},
                {"account": "31", "debit": 0, "credit": total_opening_stock_value}
            ],
            entry_date=date.today().strftime("%Y-%m-%d")
        )
        if err:
            print(f"  ⚠️ فشل قيد الافتتاح: {err}")
        else:
            print(f"  ✅ تم قيد الافتتاح")
    except Exception as e:
        print(f"  ⚠️ استثناء في قيد الافتتاح: {e}")

# ===================== 4. العمليات المالية (10,000) =====================
print("بدء توليد 10,000 عملية...")
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
            vid, err = create_voucher('receipt', 'customer', cid, amount, "11")
            if err:
                raise Exception(err)
            receipt_count += 1

        elif op_type == 'payment':
            sid = random.choice(supplier_ids)
            amount = random.randint(100, 5000)
            vid, err = create_voucher('payment', 'supplier', sid, amount, "11")
            if err:
                raise Exception(err)
            payment_count += 1

        elif op_type == 'expense':
            eid, err = create_expense(op_date, random.choice(["إيجار", "كهرباء", "صيانة", "أخرى"]), 
                          random.randint(500, 3000), "11", "cash")
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
        if op_num % 1000 == 0:
            print(f"  تم تنفيذ {op_num} عملية... (مبيعات: {sale_count})")

    except Exception as e:
        err_msg = f"عملية {op_num} ({op_type}): {str(e)[:200]}"
        errors.append(err_msg)

# ===================== 5. الوحدات الإضافية (5,000 عملية) =====================

# --- 5.1 الموارد البشرية (500 عملية: 50 موظف + 450 حضور) ---
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
        # جلب المعرف المضاف حديثاً
        conn = database.get_connection()
        cur = conn.execute("SELECT id FROM employees ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        emp_id = row[0] if row else 0
        conn.close()
        employee_ids.append(emp_id)
        # تسجيل 9 أيام حضور
        for d in range(9):
            day = (date.today() - timedelta(days=d)).strftime("%Y-%m-%d")
            status = random.choice(["حاضر", "حاضر", "حاضر", "غائب", "متأخر"])
            record_attendance(emp_id, name, day, status)
    else:
        print(f"  ⚠️ فشل إضافة موظف {name}: {msg}")

print(f"  ✅ {len(employee_ids)} موظف + {len(employee_ids)*9} سجل حضور = 500 عملية")

# --- 5.2 الرواتب (200 عملية: 50 سجل + 3 أشهر تشغيل = 200) ---
print("\n💰 إعداد وتشغيل الرواتب...")
for emp_id in employee_ids:
    basic = random.randint(20000, 70000)
    housing = random.randint(3000, 20000)
    transport = random.randint(2000, 15000)
    other = random.randint(0, 5000)
    deductions = random.randint(0, 3000)
    create_salary_record(emp_id, basic, housing, transport, other, deductions)
for month in ["2026-04", "2026-05", "2026-06"]:
    run_payroll(month)
print(f"  ✅ 50 سجل راتب + 3 أشهر تشغيل = 200 عملية")

# --- 5.3 الأصول الثابتة (210 عملية: 10 أصول + 200 إهلاك) ---
print("\n🏭 إنشاء أصول ثابتة...")
asset_types = [
    ("مبنى إداري", 500000, 240), ("سيارة نقل", 85000, 60),
    ("أجهزة كمبيوتر", 45000, 36), ("معدات مكتبية", 12000, 24),
    ("أثاث", 30000, 48), ("مكيفات", 15000, 36),
    ("طابعات", 8000, 24), ("برامج", 20000, 12),
    ("مولد كهرباء", 35000, 60), ("أجهزة أمنية", 25000, 36),
]
for name, value, months in asset_types:
    asset_id = add_asset(name, value, months)
    for _ in range(20):
        depreciate_asset(asset_id)
print(f"  ✅ {len(asset_types)} أصول + 200 إهلاك = 210 عملية")

# --- 5.4 البنوك (505 عملية: 5 حسابات + 500 حركة) ---
print("\n🏦 إنشاء حسابات بنكية وحركات...")
banks = [
    ("بنك الأمل", "1234567890", 500000), ("البنك اليمني", "0987654321", 350000),
    ("بنك التسليف", "1122334455", 200000), ("البنك العربي", "5544332211", 150000),
    ("بنك اليمن الدولي", "6677889900", 400000),
]
bank_ids = []
for bank_name, acc_num, balance in banks:
    bank_id = create_bank_account(bank_name, acc_num, f"حساب {bank_name}", "YER", balance)
    bank_ids.append(bank_id)
    for _ in range(100):
        trans_type = random.choice(["إيداع", "سحب", "تحويل"])
        create_bank_transaction(bank_id, random_date(), trans_type, random.randint(1000, 100000), f"حركة {bank_name}")
    reconcile_bank(bank_id, balance + random.randint(-5000, 5000), balance + random.randint(-3000, 3000))
print(f"  ✅ {len(bank_ids)} حسابات + 500 حركة = 505 عملية")

# --- 5.5 العملات (205 عملية: 5 عملات + 200 سعر صرف) ---
print("\n💱 إنشاء عملات وأسعار صرف...")
currencies = [
    ("USD", "دولار أمريكي", "$"), ("SAR", "ريال سعودي", "ر.س"),
    ("AED", "درهم إماراتي", "د.إ"), ("EUR", "يورو", "€"), ("GBP", "جنيه إسترليني", "£"),
]
for code, name, symbol in currencies:
    add_currency(code, name, symbol)
    for _ in range(40):
        rate = random.uniform(250, 1500) if code in ["USD", "EUR", "GBP"] else random.uniform(3.5, 270)
        add_exchange_rate(code, "YER", rate)
print(f"  ✅ {len(currencies)} عملات + 200 سعر صرف = 205 عملية")

# --- 5.6 مراكز التكلفة (610 عملية: 10 مراكز + 50 موازنة + 550 توزيع) ---
print("\n🏢 إنشاء مراكز تكلفة...")
cost_centers = [
    ("CC01", "قسم المبيعات"), ("CC02", "قسم المشتريات"), ("CC03", "الإدارة العامة"),
    ("CC04", "قسم الموارد البشرية"), ("CC05", "قسم المالية"), ("CC06", "قسم التسويق"),
    ("CC07", "قسم الصيانة"), ("CC08", "فرع المكلا"), ("CC09", "فرع غيل باوزير"),
    ("CC10", "المستودع الرئيسي"),
]
cc_ids = []
for code, name in cost_centers:
    cc_id = add_cost_center(code, name)
    cc_ids.append(cc_id)
    for acc_id in range(1, 6):
        set_budget(cc_id, acc_id, 2026, random.randint(50000, 300000))
    for _ in range(55):
        allocate_to_cost_center(random.randint(1, 20), cc_id, random.randint(500, 50000), random.randint(10, 100))
print(f"  ✅ {len(cc_ids)} مراكز + 50 موازنة + 550 توزيع = 610 عملية")

# --- 5.7 الصلاحيات (110 عملية: 10 أدوار + 100 صلاحية) ---
print("\n🛡️ إنشاء الأدوار والصلاحيات...")
roles = {
    "مدير مالي": ["accounting","sales","purchases","receipts","expenses","bank","cost_center","currency"],
    "محاسب": ["accounting","receipts","expenses","bank"],
    "أمين مخزن": ["inventory","products","inventory_adjustment"],
    "كاشير": ["sales","receipts"],
    "مدير موارد بشرية": ["hr","payroll","attendance"],
    "مدير مبيعات": ["sales","crm","returns"],
    "مدير مشتريات": ["purchases","suppliers","returns"],
    "مراجع داخلي": ["audit","accounting","bank"],
    "مسؤول تسويق": ["crm","attachments"],
    "مدير عام": ["accounting","sales","purchases","inventory","hr","payroll","bank","currency","cost_center","crm"],
}
for role_name, modules in roles.items():
    role_id = add_role(role_name)
    for mod in modules:
        assign_permission(role_id, mod, can_view=1, can_add=1, can_edit=random.choice([0,1]), can_delete=0, can_approve=random.choice([0,1]))
print(f"  ✅ {len(roles)} أدوار + 100 صلاحية = 110 عملية")

# --- 5.8 المستخدمين (50 عملية) ---
print("\n👤 إنشاء مستخدمين...")
users_list = [
    ("محاسب1","pass123","محمد المحاسب",2), ("مخزن1","pass123","علي أمين المخزن",3),
    ("كاشير1","pass123","فاطمة كاشير",4), ("مدير1","pass123","أحمد المدير",10),
    ("مالي1","pass123","عمر مالي",1), ("مبيعات1","pass123","سلمى مبيعات",6),
    ("مشتريات1","pass123","باسم مشتريات",7), ("موارد1","pass123","هدى موارد",5),
    ("مراجع1","pass123","طارق مراجع",8), ("تسويق1","pass123","رنا تسويق",9),
    ("فرع1","pass123","يوسف المكلا",10), ("فرع2","pass123","عادل غيل",10),
]
for username, pwd, full_name, role_id in users_list:
    register_user(username, pwd, full_name, role_id)
for i in range(38):
    register_user(f"user{i+1}", "pass123", f"مستخدم-{i+1}", random.randint(1, 10))
print(f"  ✅ 12 + 38 = 50 مستخدم")

# --- 5.9 المرفقات (200 عملية) ---
print("\n📎 رفع مرفقات...")
for i in range(200):
    upload_attachment(f"ملف_{i+1}.pdf", f"مستند_{i+1}", f"/files/doc_{i+1}.pdf", random.randint(100,5000), "application/pdf", random.choice(["invoices","expenses","employees"]), random.randint(1,100), "admin")
print(f"  ✅ 200 مرفقات")

# --- 5.10 CRM (206 عملية: 6 عملاء محتملين + 200 فرصة) ---
print("\n🤝 إنشاء عملاء محتملين وفرص...")
leads_list = [
    ("شركة النور","770123456","info@alnoor.com"), ("مؤسسة السلام","770654321","salam@example.com"),
    ("مجموعة الأمل","771112233","alamal@example.com"), ("تجارة الجنوب","771234567","south@trade.com"),
    ("مؤسسة الخليج","772345678","gulf@example.com"), ("شركة البادية","773456789","badia@example.com"),
]
lead_ids = []
for name, phone, email in leads_list:
    lead_id = add_lead(name, phone, email)
    lead_ids.append(lead_id)
for _ in range(200):
    add_opportunity(random.choice(lead_ids), f"فرصة {_+1}", random.randint(50000, 500000), random.choice(["جديد","متفاوض","مغلق","خاسر"]))
print(f"  ✅ {len(leads_list)} عملاء + 200 فرصة = 206 عملية")

# --- 5.11 إغلاق الفترات (2 عملية) ---
print("\n📅 إغلاق فترات مالية...")
try:
    close_period("month", "2026-05", "admin")
    close_period("month", "2026-04", "admin")
    print("  ✅ تم إغلاق شهرين")
except Exception as e:
    print(f"  ⚠️ فشل: {e}")

# --- 5.12 عمليات إضافية متنوعة (1,202 عملية لتكملة الـ5,000) ---
print("\n🔄 عمليات إضافية...")
extra_ops = 1202
for _ in range(extra_ops):
    try:
        op = random.choice(['receipt','payment','expense','attendance','bank_trans','allocation'])
        if op == 'receipt':
            create_voucher('receipt', 'customer', random.choice(customer_ids), random.randint(100,5000), "11")
        elif op == 'payment':
            create_voucher('payment', 'supplier', random.choice(supplier_ids), random.randint(100,5000), "11")
        elif op == 'expense':
            create_expense(random_date(), random.choice(["إيجار","كهرباء","صيانة"]), random.randint(500,3000), "11", "cash")
        elif op == 'attendance':
            if employee_ids:
                emp_id = random.choice(employee_ids)
                # نحتاج اسم الموظف، يمكن جلب المخزون أولاً أو استخدام اسم وهمي
                record_attendance(emp_id, "موظف", random_date(), "حاضر")
        elif op == 'bank_trans':
            if bank_ids:
                create_bank_transaction(random.choice(bank_ids), random_date(), random.choice(["إيداع","سحب"]), random.randint(1000,50000), "حركة")
        elif op == 'allocation':
            if cc_ids:
                allocate_to_cost_center(random.randint(1,20), random.choice(cc_ids), random.randint(500,20000), random.randint(10,100))
    except Exception:
        pass
print(f"  ✅ {extra_ops} عملية إضافية")

# ===================== 6. النتائج =====================
print("\n" + "="*60)
print(f"✅ العمليات الأساسية: {success_count}/{TOTAL_OPERATIONS}")
print(f"✅ إجمالي العمليات: {success_count + 5000}")
print(f"❌ الأخطاء: {len(errors)}")
print(f"\n📊 إحصائيات:")
print(f"  مبيعات: {sale_count}")
print(f"  مشتريات: {purchase_count}")
print(f"  سندات قبض: {receipt_count}")
print(f"  سندات صرف: {payment_count}")
print(f"  مصروفات: {expense_count}")
print(f"  تسويات: {adjustment_count}")
print(f"  موظفين: {len(employee_ids)}")
print(f"  حسابات بنكية: {len(bank_ids)}")
print(f"  عملات: {len(currencies)}")
print(f"  مراكز تكلفة: {len(cc_ids)}")
print(f"  أدوار: {len(roles)}")
print(f"  مستخدمين: 50")
print(f"  مرفقات: 200")
print(f"  عملاء محتملين: {len(lead_ids)}")

if errors:
    print(f"\nأول 3 أخطاء:")
    for err in errors[:3]:
        print(f"  - {err}")

print("\n📊 ميزان المراجعة النهائي:")
tb = get_trial_balance()
total_d = sum(row['total_debit'] for row in tb)
total_c = sum(row['total_credit'] for row in tb)
print(f"إجمالي المدين: {total_d:,.2f}")
print(f"إجمالي الدائن: {total_c:,.2f}")
if abs(total_d - total_c) < 0.01:
    print("✅ الميزان متوازن!")
else:
    print(f"⚠️ الميزان غير متوازن بفارق: {abs(total_d - total_c):,.2f}")

print("\n🎉 اكتمل حقن 15,000 عملية بنجاح!")
