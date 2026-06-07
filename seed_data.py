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
from services.accounting_service import get_trial_balance

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
    
    # تحقق إذا كانت الحسابات موجودة
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
            pass  # تجاهل إذا كان الحساب موجوداً
    
    conn.commit()
    conn.close()
    print("✅ تم إنشاء شجرة الحسابات")

# ===================== تشخيص تلقائي =====================
def diagnostic():
    """فحص سريع للتأكد من أن الخدمات تعمل"""
    print("🔍 تشخيص النظام...")
    try:
        # اختبار إضافة عميل
        cid = add_customer("اختبار_تشخيص", "770000000", "عنوان")
        # اختبار إضافة مورد
        sid = add_supplier("اختبار_مورد", "771111111", "عنوان")
        # اختبار إضافة منتج
        add_product("منتج_تشخيص", None, "عام", 100, 200, 100, 10)
        # اختبار شراء
        items_p = [{"product_id": 1, "quantity": 10, "unit_price_base": 100}]
        inv_p, _, err_p = create_purchase_invoice(sid, items_p)
        if err_p:
            print(f"❌ فشل شراء: {err_p}")
            return False
        # اختبار بيع
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
purchase_errors = 0
for pid in product_ids:
    sid = random.choice(supplier_ids)
    cost = random.randint(50, 500)
    qty = random.randint(50, 200)
    items = [{"product_id": pid, "quantity": qty, "unit_price_base": cost}]
    try:
        inv_id, _, err = create_purchase_invoice(sid, items, currency_code="YER")
        if err:
            purchase_errors += 1
    except Exception as e:
        purchase_errors += 1

print(f"  اكتمل. أخطاء الشراء الافتتاحي: {purchase_errors}")

# ===================== 4. العمليات المالية =====================
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

# ===================== 5. النتائج =====================
print("\n" + "="*60)
print(f"✅ العمليات الناجحة: {success_count}/{TOTAL_OPERATIONS}")
print(f"❌ الأخطاء: {len(errors)}")
print(f"\n📊 إحصائيات:")
print(f"  مبيعات: {sale_count}")
print(f"  مشتريات: {purchase_count}")
print(f"  سندات قبض: {receipt_count}")
print(f"  سندات صرف: {payment_count}")
print(f"  مصروفات: {expense_count}")
print(f"  تسويات: {adjustment_count}")

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
