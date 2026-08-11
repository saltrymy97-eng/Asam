import os
import sys
import random
import sqlite3
from datetime import datetime, timedelta

# ضمان التعرف على مسار الجذر في Streamlit Cloud
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 1. الاستيرادات المحدثة وفقاً لأسماء ملفات مشروعك الحقيقية
import database
from services.chart_service import get_functional_account
from services.purchases_service import create_purchase_invoice
from services.sales_service import create_sales_invoice
from services.receipts_service import create_receipt_voucher, create_payment_voucher
from services.expenses_service import create_expense
from services.inventory_adjustment_service import create_inventory_adjustment


def ensure_base_currency():
    """التأكد من وجود العملة الأساسية (الريال اليمني)"""
    conn = database.get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM currencies WHERE code = 'YER'")
    row = c.fetchone()
    if not row:
        c.execute(
            "INSERT INTO currencies (code, name, symbol, is_base, is_active) VALUES ('YER', 'ريال يمني', 'ر.ي', 1, 1)"
        )
        conn.commit()
    conn.close()


def safe_add_product(name, barcode, category, purchase_price, selling_price, quantity, reorder_level=10):
    """دالة إضافة منتج معدلة تُرجع الـ ID الحقيقي من قاعدة البيانات"""
    conn = database.get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO products (name, barcode, category, purchase_price, selling_price, quantity, reorder_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (name, barcode, category, purchase_price, selling_price, quantity, reorder_level))
        product_id = c.lastrowid
        conn.commit()
        return product_id
    except sqlite3.Error as e:
        conn.rollback()
        print(f"[خطأ إضافة منتج]: {e}")
        return None
    finally:
        conn.close()


def run_seeder(num_transactions=10000):
    print("🚀 بدء عملية تغذية واختبار قاعدة البيانات (Seeding & Stress Test)...")
    
    # تهيئة قاعدة البيانات والعملة الأساسية
    database.init_db()
    database.create_default_admin()
    ensure_base_currency()

    # 2. التحقق الجوهري من وجود الحسابات المالية قبل البدء
    cash_account_id = get_functional_account('cash')
    inventory_account_id = get_functional_account('inventory')
    capital_account_id = get_functional_account('capital')
    operating_expense_account_id = (
        get_functional_account('operating_expenses') or 
        get_functional_account('general_expense')
    )

    required_accounts = {
        "النقدية (cash)": cash_account_id,
        "المخزون (inventory)": inventory_account_id,
        "رأس المال (capital)": capital_account_id,
        "المصروفات (operating_expenses)": operating_expense_account_id
    }

    for name, acc_id in required_accounts.items():
        if acc_id is None:
            raise ValueError(f"❌ خطأ قاطع: حساب ({name}) غير محدد في شجرة الحسابات! يرجى تهيئة الشجرة أولاً.")

    # 3. إدخال الموردين والعملاء
    conn = database.get_connection()
    c = conn.cursor()
    
    supplier_ids = []
    for i in range(1, 21):
        c.execute("INSERT INTO suppliers (name, phone, address) VALUES (?, ?, ?)", 
                  (f"مورد {i}", f"7700000{i:02d}", f"صنعاء - شارع {i}"))
        supplier_ids.append(c.lastrowid)

    customer_ids = []
    for i in range(1, 51):
        c.execute("INSERT INTO customers (name, phone, address) VALUES (?, ?, ?)", 
                  (f"عميل {i}", f"7300000{i:02d}", f"عدن - شارع {i}"))
        customer_ids.append(c.lastrowid)

    conn.commit()
    conn.close()

    # 4. إدخال المنتجات مع الاحتفاظ بالـ IDs الحقيقية ورصيد افتتاحي بسيط لمنع العجز
    product_ids = []
    for i in range(200):
        cost = round(random.uniform(500, 50000), 2)
        price = round(cost * random.uniform(1.15, 1.40), 2)
        p_id = safe_add_product(f"منتج-{i+1}", f"BAR-{1000+i}", "عام", cost, price, random.randint(20, 50), 10)
        if p_id:
            product_ids.append(p_id)

    print(f"✅ تم تجهيز: {len(supplier_ids)} موردين، {len(customer_ids)} عملاء، و {len(product_ids)} منتجات.")

    # إحصائيات الأخطاء والنجاح
    stats = {
        'purchase': 0, 'sale': 0, 'receipt': 0, 
        'payment': 0, 'expense': 0, 'adjustment': 0,
        'errors': 0
    }

    start_date = datetime.now() - timedelta(days=365)

    # 5. حلقة التغذية الرئيسية (10,000 عملية)
    for i in range(num_transactions):
        current_date = (start_date + timedelta(minutes=i * 5)).strftime('%Y-%m-%d %H:%M:%S')
        
        op_type = random.choices(
            ['purchase', 'sale', 'receipt', 'payment', 'expense', 'adjustment'],
            weights=[30, 50, 8, 5, 5, 2]
        )[0]

        try:
            if op_type == 'purchase':
                sup_id = random.choice(supplier_ids)
                p_id = random.choice(product_ids)
                qty = random.randint(10, 100)
                cost = round(random.uniform(500, 50000), 2)
                
                inv_id, total, err = create_purchase_invoice(
                    supplier_id=sup_id,
                    items=[{'product_id': p_id, 'quantity': qty, 'unit_price': cost}],
                    currency_code='YER',
                    exchange_rate=1.0,
                    invoice_date=current_date
                )
                if err:
                    stats['errors'] += 1
                else:
                    stats['purchase'] += 1

            elif op_type == 'sale':
                cust_id = random.choice(customer_ids)
                p_id = random.choice(product_ids)
                qty = random.randint(1, 5)
                price = round(random.uniform(600, 60000), 2)

                inv_id, total, err = create_sales_invoice(
                    customer_id=cust_id,
                    items=[{'product_id': p_id, 'quantity': qty, 'unit_price': price}],
                    currency_code='YER',
                    exchange_rate=1.0,
                    invoice_date=current_date
                )
                if err:
                    stats['errors'] += 1
                else:
                    stats['sale'] += 1

            elif op_type == 'receipt':
                cust_id = random.choice(customer_ids)
                amount = round(random.uniform(1000, 100000), 2)
                v_id, err = create_receipt_voucher(
                    party_type='customer',
                    party_id=cust_id,
                    amount=amount,
                    account_code=cash_account_id,
                    date_str=current_date,
                    notes=f"سند قبض تلقائي #{i+1}"
                )
                if err:
                    stats['errors'] += 1
                else:
                    stats['receipt'] += 1

            elif op_type == 'payment':
                sup_id = random.choice(supplier_ids)
                amount = round(random.uniform(1000, 100000), 2)
                v_id, err = create_payment_voucher(
                    party_type='supplier',
                    party_id=sup_id,
                    amount=amount,
                    account_code=cash_account_id,
                    date_str=current_date,
                    notes=f"سند صرف تلقائي #{i+1}"
                )
                if err:
                    stats['errors'] += 1
                else:
                    stats['payment'] += 1

            elif op_type == 'expense':
                amount = round(random.uniform(500, 20000), 2)
                exp_id, err = create_expense(
                    category="مصروفات تشغيلية",
                    amount=amount,
                    account_code=operating_expense_account_id,
                    payment_method="cash",
                    date_str=current_date,
                    notes=f"مصروف تشغيلي تلقائي #{i+1}"
                )
                if err:
                    stats['errors'] += 1
                else:
                    stats['expense'] += 1

            elif op_type == 'adjustment':
                p_id = random.choice(product_ids)
                actual_qty = random.randint(10, 50)
                adj_id, err = create_inventory_adjustment(
                    product_id=p_id,
                    actual_qty=actual_qty,
                    reason="تسوية جردية دورية",
                    date_str=current_date
                )
                if err:
                    stats['errors'] += 1
                else:
                    stats['adjustment'] += 1

        except Exception as e:
            stats['errors'] += 1

        # طباعة مؤشر التقدم كل 1000 عملية
        if (i + 1) % 1000 == 0:
            print(f"⏳ تم تنفيذ {i+1} عملية من أصل {num_transactions}...")

    # 6. التقرير النهائي
    print("\n🎉 اكتملت عملية التغذية والاختبار بنجاح!")
    print("📊 ملخص العمليات المضافة:")
    print(f" - فواتير الشراء: {stats['purchase']}")
    print(f" - فواتير البيع: {stats['sale']}")
    print(f" - سندات القبض: {stats['receipt']}")
    print(f" - سندات الصرف: {stats['payment']}")
    print(f" - المصروفات: {stats['expense']}")
    print(f" - التسويات الجردية: {stats['adjustment']}")
    print(f" ⚠️ إجمالي الأخطاء/العمليات المرفوضة: {stats['errors']}")


if __name__ == "__main__":
    run_seeder(10000)
