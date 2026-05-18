import streamlit as st
import sqlite3
import pandas as pd

DB_PATH = "erp.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_fifo_tables():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            quantity REAL NOT NULL,
            unit_cost REAL NOT NULL,
            batch_date TEXT NOT NULL,
            reference TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fifo_consumptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER,
            consumed_qty REAL NOT NULL,
            consumption_date TEXT NOT NULL,
            reference TEXT,
            FOREIGN KEY (batch_id) REFERENCES inventory_batches(id)
        )
    """)
    conn.commit()
    conn.close()

def add_batch(product_id, quantity, unit_cost, batch_date, reference=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO inventory_batches (product_id, quantity, unit_cost, batch_date, reference) VALUES (?,?,?,?,?)",
        (product_id, quantity, unit_cost, batch_date, reference)
    )
    conn.commit()
    conn.close()

def get_available_batches(product_id):
    conn = get_conn()
    # استخدام dict_factory للحصول على قواميس حقيقية
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("""
        SELECT b.*, 
               b.quantity - COALESCE(SUM(c.consumed_qty), 0) as remaining
        FROM inventory_batches b
        LEFT JOIN fifo_consumptions c ON b.id = c.batch_id
        WHERE b.product_id = ?
        GROUP BY b.id
        HAVING remaining > 0
        ORDER BY b.batch_date ASC, b.id ASC
    """, (product_id,))
    batches = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return batches

def consume_fifo(product_id, quantity, consumption_date, reference=""):
    batches = get_available_batches(product_id)
    total_cost = 0.0
    remaining_to_consume = quantity
    conn = get_conn()

    for batch in batches:
        if remaining_to_consume <= 0:
            break
        qty_available = batch["remaining"]
        qty_to_take = min(qty_available, remaining_to_consume)
        cost = qty_to_take * batch["unit_cost"]
        total_cost += cost

        conn.execute(
            "INSERT INTO fifo_consumptions (batch_id, consumed_qty, consumption_date, reference) VALUES (?,?,?,?)",
            (batch["id"], qty_to_take, consumption_date, reference)
        )
        remaining_to_consume -= qty_to_take

    if remaining_to_consume > 0:
        conn.rollback()
        conn.close()
        return None, remaining_to_consume

    conn.commit()
    conn.close()
    return total_cost, 0

def get_product_cost(product_id):
    batches = get_available_batches(product_id)
    total = sum(b["remaining"] * b["unit_cost"] for b in batches)
    return total

def show():
    st.title("📦 FIFO للمخزون")
    create_fifo_tables()
    conn = get_conn()
    products = pd.read_sql_query("SELECT id, name FROM products", conn)
    conn.close()

    if products.empty:
        st.warning("لا توجد منتجات. أضف منتجات من وحدة المخزون أولاً.")
        return

    tab1, tab2, tab3 = st.tabs(["➕ دفعات شراء", "🔄 استهلاك FIFO", "📋 الدفعات المتبقية"])

    with tab1:
        st.subheader("إضافة دفعة شراء")
        prod_name = st.selectbox("المنتج", products["name"], key="fifo_batch_prod")
        prod_id = int(products[products["name"] == prod_name]["id"].iloc[0])
        col1, col2 = st.columns(2)
        qty = col1.number_input("الكمية", min_value=0.0, step=1.0)
        cost = col2.number_input("تكلفة الوحدة", min_value=0.0, step=0.01)
        bdate = st.date_input("تاريخ الدفعة")
        ref = st.text_input("مرجع (اختياري)")
        if st.button("إضافة الدفعة"):
            if qty > 0 and cost > 0:
                add_batch(prod_id, qty, cost, bdate.strftime("%Y-%m-%d"), ref)
                st.success("تمت إضافة الدفعة")
                st.rerun()
            else:
                st.error("الكمية والتكلفة يجب أن تكون أكبر من صفر")

    with tab2:
        st.subheader("استهلاك المخزون (FIFO)")
        prod_name = st.selectbox("المنتج", products["name"], key="fifo_consume_prod")
        prod_id = int(products[products["name"] == prod_name]["id"].iloc[0])
        available = sum(b["remaining"] for b in get_available_batches(prod_id))
        st.write(f"الكمية المتاحة: {available:.2f}")
        qty_consume = st.number_input("الكمية المطلوب صرفها", min_value=0.0, step=1.0)
        cons_date = st.date_input("تاريخ الصرف", key="fifo_consume_date")
        cons_ref = st.text_input("مرجع الصرف", key="fifo_consume_ref")
        if st.button("تسجيل الصرف"):
            if qty_consume <= 0:
                st.error("الكمية يجب أن تكون أكبر من صفر")
            elif qty_consume > available:
                st.error("الكمية المطلوبة أكبر من المتاح")
            else:
                total_cost, shortage = consume_fifo(prod_id, qty_consume,
                                                    cons_date.strftime("%Y-%m-%d"),
                                                    cons_ref)
                if shortage > 0:
                    st.error("فشل: الكمية غير كافية")
                else:
                    st.success(f"تم الصرف. التكلفة الإجمالية: {total_cost:,.2f}")
                    st.rerun()

    with tab3:
        st.subheader("الدفعات المتبقية")
        prod_name = st.selectbox("المنتج", products["name"], key="fifo_view_prod")
        prod_id = int(products[products["name"] == prod_name]["id"].iloc[0])
        batches = get_available_batches(prod_id)
        if batches:
            df = pd.DataFrame(batches)
            # التحقق من وجود الأعمدة المطلوبة
            if 'remaining' in df.columns and 'unit_cost' in df.columns:
                df = df.rename(columns={"batch_date": "التاريخ", "remaining": "الكمية المتبقية",
                                        "unit_cost": "تكلفة الوحدة", "reference": "المرجع"})
                df["القيمة"] = df["الكمية المتبقية"] * df["تكلفة الوحدة"]
                st.dataframe(df[["التاريخ", "الكمية المتبقية", "تكلفة الوحدة", "القيمة", "المرجع"]],
                             use_container_width=True, hide_index=True)
                total_cost = df["القيمة"].sum()
                st.markdown(f"**إجمالي قيمة المخزون المتبقي: {total_cost:,.2f}**")
            else:
                st.warning("لم يتم العثور على بيانات المخزون المطلوبة")
        else:
            st.info("لا توجد دفعات متبقية لهذا المنتج")
