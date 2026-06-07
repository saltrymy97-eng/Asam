import database
database.init_db()

import random
import sys
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

# ===================== 1. العملاء والموردين =====================
print("إنشاء العملاء والموردين...")
customer_ids = []
for i in range(50):
    cid = add_customer(f"عميل-{i+1}", random_phone(), f"عنوان-{i+1}")
    customer_ids.append(cid)

supplier_ids = []
for i in range(50):
    sid = add_supplier(f"مورد-{i+1}", random_phone(), f"عنوان-{i+1}")
    supplier_ids.append(sid)

# ===================== 2. المنتجات والمخزون الافتتاحي =====================
print("إنشاء المنتجات...")
product_ids = []
for i in range(200):
    cost = random.randint(10, 500)
    price = cost + random.randint(5, 300)
    add_product(f"منتج-{i+1}", None, "عام", cost, price, 0, 10)
    product_ids.append(i+1)

# ===================== 3. شراء مخزون افتتاحي =====================
print("شراء مخزون افتتاحي...")
for pid in product_ids:
    sid = random.choice(supplier_ids)
    cost = random.randint(50, 500)
    qty = random.randint(50, 200)
    # ✅ إصلاح: استخدام unit_price_base بدل unit_price
    items = [{"product_id": pid, "quantity": qty, "unit_price_base": cost}]
    try:
        create_purchase_invoice(sid, items, currency_code="YER")
    except:
        pass

# ===================== 4. العمليات المالية =====================
print("بدء توليد 10,000 عملية...")
errors = []
success_count = 0

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
            # ✅ إصلاح: استخدام unit_price_base بدل unit_price
            items = [{"product_id": pid, "quantity": qty, "unit_price_base": price}]
            create_purchase_invoice(sid, items, currency_code="YER")

        elif op_type == 'sale':
            cid = random.choice(customer_ids)
            pid = random.choice(product_ids)
            qty = random.randint(1, 5)
            price = random.randint(100, 1000)
            items = [{"product_id": pid, "quantity": qty, "unit_price_base": price}]
            create_sale_invoice(cid, items, currency_code="YER")

        elif op_type == 'receipt':
            cid = random.choice(customer_ids)
            amount = random.randint(100, 5000)
            create_voucher('receipt', 'customer', cid, amount, "11")

        elif op_type == 'payment':
            sid = random.choice(supplier_ids)
            amount = random.randint(100, 5000)
            create_voucher('payment', 'supplier', sid, amount, "11")

        elif op_type == 'expense':
            create_expense(op_date, random.choice(["إيجار", "كهرباء", "صيانة", "أخرى"]), 
                          random.randint(500, 3000), "11", "cash")

        elif op_type == 'adjustment':
            pid = random.choice(product_ids)
            diff = random.randint(-5, 5)
            if diff != 0:
                try:
                    create_adjustment(pid, 10, 10 + diff)
                except:
                    pass

        success_count += 1
        if op_num % 1000 == 0:
            print(f"  تم تنفيذ {op_num} عملية...")

    except Exception as e:
        err_msg = f"عملية {op_num} ({op_type}): {str(e)[:200]}"
        errors.append(err_msg)
        print(f"❌ {err_msg}")

# ===================== 5. النتائج =====================
print("\n" + "="*60)
print(f"✅ العمليات الناجحة: {success_count}/{TOTAL_OPERATIONS}")
print(f"❌ الأخطاء: {len(errors)}")
if errors:
    print("\nأول 5 أخطاء:")
    for err in errors[:5]:
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
