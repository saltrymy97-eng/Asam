# ui/fifo_ui.py
# واجهة FIFO احترافية - إصدار الاختبار والتشغيل التجاري

import streamlit as st
import pandas as pd
from datetime import date

from services.fifo_service import (
    create_fifo_tables,
    add_batch,
    get_available_batches,
    consume_fifo,
    get_products_for_select,
)


# =========================================================
# الألوان
# =========================================================

TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"

ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"


# =========================================================
# أدوات مساعدة
# =========================================================

def money(value):
    """تنسيق المبالغ."""
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return "0.00"


def get_fifo_preview(batches, quantity):
    """
    معاينة الدفعات التي سيتم استهلاكها حسب FIFO.
    لا تعدل قاعدة البيانات.
    """
    remaining = float(quantity)
    preview = []
    total_cost = 0.0

    for batch in batches:
        if remaining <= 0:
            break

        available = float(batch["remaining"])
        take = min(available, remaining)

        cost = take * float(batch["unit_cost"])

        preview.append({
            "id": batch["id"],
            "date": batch["batch_date"],
            "available": available,
            "quantity": take,
            "unit_cost": float(batch["unit_cost"]),
            "cost": cost,
            "reference": batch.get("reference", "")
        })

        total_cost += cost
        remaining -= take

    return preview, total_cost, remaining


# =========================================================
# الواجهة الرئيسية
# =========================================================

def show():

    # -----------------------------------------------------
    # تهيئة الجداول
    # -----------------------------------------------------

    create_fifo_tables()

    # حماية من الضغط المتكرر
    if "fifo_saving_batch" not in st.session_state:
        st.session_state.fifo_saving_batch = False

    if "fifo_consuming" not in st.session_state:
        st.session_state.fifo_consuming = False

    # -----------------------------------------------------
    # العنوان
    # -----------------------------------------------------

    st.markdown(
        f"""
        <div style="
            padding: 1.5rem 2rem;
            margin-bottom: 1.5rem;
            border-radius: 18px;
            background: rgba(255,255,255,0.07);
            border: 1px solid rgba(255,255,255,0.15);
            box-shadow: 0 8px 32px rgba(0,0,0,0.25);
            text-align: right;
        ">
            <h1 style="
                color:{TEXT_PRIMARY};
                font-size:2.5rem;
                margin:0;
                text-shadow:0 0 18px {ACCENT_PURPLE};
            ">
                📦 إدارة FIFO للمخزون
            </h1>

            <p style="
                color:{TEXT_SECONDARY};
                font-size:1.05rem;
                margin-top:0.5rem;
            ">
                الوارد أولاً صادر أولاً — تتبع طبقات التكلفة وحساب تكلفة الصرف
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # -----------------------------------------------------
    # جلب المنتجات
    # -----------------------------------------------------

    products = get_products_for_select()

    if not products:
        st.warning(
            "لا توجد منتجات حالياً. "
            "أضف منتجات من وحدة المخزون أولاً."
        )
        return

    product_dict = {
        p["id"]: p["name"]
        for p in products
    }

    product_ids = list(product_dict.keys())

    # -----------------------------------------------------
    # التبويبات
    # -----------------------------------------------------

    tab1, tab2, tab3 = st.tabs(
        [
            "➕ إضافة دفعة",
            "🔄 استهلاك FIFO",
            "📊 المخزون والطبقات",
        ]
    )

    # =====================================================
    # 1 - إضافة دفعة
    # =====================================================

    with tab1:

        st.markdown(
            f"""
            <h3 style="color:{ACCENT_GREEN};">
                ➕ إضافة طبقة مخزون جديدة
            </h3>
            <p style="color:{TEXT_SECONDARY};">
                تمثل كل دفعة شراء طبقة مستقلة لها كمية وتكلفة وتاريخ خاص بها.
            </p>
            """,
            unsafe_allow_html=True
        )

        st.divider()

        prod_id = st.selectbox(
            "المنتج",
            options=product_ids,
            format_func=lambda x: product_dict[x],
            key="fifo_batch_product"
        )

        col1, col2 = st.columns(2)

        with col1:
            quantity = st.number_input(
                "الكمية",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key="fifo_batch_quantity"
            )

        with col2:
            unit_cost = st.number_input(
                "تكلفة الوحدة",
                min_value=0.0,
                value=0.0,
                step=0.01,
                key="fifo_batch_cost"
            )

        col3, col4 = st.columns(2)

        with col3:
            batch_date = st.date_input(
                "تاريخ الدفعة",
                value=date.today(),
                key="fifo_batch_date"
            )

        with col4:
            reference = st.text_input(
                "مرجع الدفعة",
                placeholder="مثال: فاتورة شراء #1001",
                key="fifo_batch_reference"
            )

        # -------------------------------------------------
        # معاينة قيمة الدفعة
        # -------------------------------------------------

        batch_value = quantity * unit_cost

        st.markdown(
            f"""
            <div style="
                padding:1rem;
                margin:1rem 0;
                border-radius:12px;
                background:rgba(16,185,129,0.10);
                border:1px solid rgba(16,185,129,0.25);
                text-align:right;
            ">
                <span style="color:{TEXT_SECONDARY};">
                    قيمة الدفعة
                </span>
                <br>
                <strong style="
                    color:{ACCENT_GREEN};
                    font-size:1.5rem;
                ">
                    {money(batch_value)}
                </strong>
            </div>
            """,
            unsafe_allow_html=True
        )

        # -------------------------------------------------
        # حفظ الدفعة
        # -------------------------------------------------

        if st.button(
            "💾 إضافة الدفعة",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.fifo_saving_batch,
            key="fifo_add_batch_button"
        ):

            st.session_state.fifo_saving_batch = True

            if quantity <= 0:
                st.error("❌ يجب أن تكون الكمية أكبر من صفر.")

            elif unit_cost <= 0:
                st.error("❌ يجب أن تكون تكلفة الوحدة أكبر من صفر.")

            else:

                success, error = add_batch(
                    product_id=prod_id,
                    quantity=quantity,
                    unit_cost=unit_cost,
                    batch_date=batch_date.strftime("%Y-%m-%d"),
                    reference=reference
                )

                if success:
                    st.success(
                        f"✅ تمت إضافة الدفعة بنجاح — "
                        f"الكمية: {quantity:,.2f} | "
                        f"التكلفة: {money(unit_cost)}"
                    )
                    st.session_state.fifo_saving_batch = False
                    st.rerun()

                else:
                    st.error(f"❌ فشل إضافة الدفعة: {error}")

            st.session_state.fifo_saving_batch = False

    # =====================================================
    # 2 - استهلاك FIFO
    # =====================================================

    with tab2:

        st.markdown(
            f"""
            <h3 style="color:{ACCENT_ORANGE};">
                🔄 استهلاك المخزون حسب FIFO
            </h3>
            <p style="color:{TEXT_SECONDARY};">
                سيبدأ النظام باستهلاك أقدم دفعة متاحة أولاً، ثم ينتقل إلى الدفعات التالية عند الحاجة.
            </p>
            """,
            unsafe_allow_html=True
        )

        st.divider()

        prod_id = st.selectbox(
            "المنتج",
            options=product_ids,
            format_func=lambda x: product_dict[x],
            key="fifo_consume_product"
        )

        # -------------------------------------------------
        # الدفعات الحالية
        # -------------------------------------------------

        batches = get_available_batches(prod_id)

        available_quantity = sum(
            float(batch["remaining"])
            for batch in batches
        )

        inventory_value = sum(
            float(batch["remaining"]) *
            float(batch["unit_cost"])
            for batch in batches
        )

        # -------------------------------------------------
        # بطاقات المعلومات
        # -------------------------------------------------

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "الكمية المتاحة",
                f"{available_quantity:,.2f}"
            )

        with col2:
            st.metric(
                "عدد الطبقات",
                len(batches)
            )

        with col3:
            st.metric(
                "قيمة المخزون",
                money(inventory_value)
            )

        st.divider()

        # -------------------------------------------------
        # كمية الصرف
        # -------------------------------------------------

        quantity = st.number_input(
            "الكمية المطلوب صرفها",
            min_value=0.0,
            max_value=float(available_quantity)
            if available_quantity > 0
            else 0.0,
            value=0.0,
            step=1.0,
            key="fifo_consume_quantity"
        )

        reference = st.text_input(
            "مرجع الصرف",
            placeholder="مثال: فاتورة مبيعات #2050",
            key="fifo_consume_reference"
        )

        st.caption(
            "ملاحظة: الخدمة الحالية تسجل تاريخ الاستهلاك تلقائياً بتاريخ تنفيذ العملية."
        )

        # -------------------------------------------------
        # معاينة FIFO
        # -------------------------------------------------

        if quantity > 0 and quantity <= available_quantity:

            preview, estimated_cost, remaining = get_fifo_preview(
                batches,
                quantity
            )

            st.markdown(
                f"""
                <h4 style="color:{ACCENT_BLUE};">
                    🔍 معاينة عملية FIFO
                </h4>
                """,
                unsafe_allow_html=True
            )

            preview_df = pd.DataFrame([
                {
                    "الدفعة": row["id"],
                    "تاريخ الدفعة": row["date"],
                    "الكمية المتاحة": row["available"],
                    "الكمية المستهلكة": row["quantity"],
                    "تكلفة الوحدة": row["unit_cost"],
                    "تكلفة الطبقة": row["cost"],
                    "المرجع": row["reference"]
                }
                for row in preview
            ])

            if not preview_df.empty:

                st.dataframe(
                    preview_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "الكمية المتاحة": st.column_config.NumberColumn(
                            format="%.2f"
                        ),
                        "الكمية المستهلكة": st.column_config.NumberColumn(
                            format="%.2f"
                        ),
                        "تكلفة الوحدة": st.column_config.NumberColumn(
                            format="%.2f"
                        ),
                        "تكلفة الطبقة": st.column_config.NumberColumn(
                            format="%.2f"
                        )
                    }
                )

            # -------------------------------------------------
            # التكلفة المتوقعة
            # -------------------------------------------------

            st.markdown(
                f"""
                <div style="
                    padding:1.2rem;
                    margin:1rem 0;
                    border-radius:14px;
                    background:rgba(245,158,11,0.10);
                    border:1px solid rgba(245,158,11,0.30);
                    text-align:right;
                ">
                    <div style="color:{TEXT_SECONDARY};">
                        تكلفة الصرف حسب FIFO
                    </div>

                    <div style="
                        color:{ACCENT_ORANGE};
                        font-size:2rem;
                        font-weight:bold;
                    ">
                        {money(estimated_cost)}
                    </div>

                    <div style="
                        color:{TEXT_SECONDARY};
                        margin-top:0.3rem;
                    ">
                        متوسط تكلفة الوحدة:
                        {money(estimated_cost / quantity)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            # -------------------------------------------------
            # زر التنفيذ
            # -------------------------------------------------

            if st.button(
                "🔒 تأكيد وتسجيل الصرف",
                type="primary",
                use_container_width=True,
                disabled=st.session_state.fifo_consuming,
                key="fifo_consume_button"
            ):

                st.session_state.fifo_consuming = True

                total_cost, error = consume_fifo(
                    product_id=prod_id,
                    quantity=quantity,
                    reference=reference
                )

                if error:
                    st.error(
                        f"❌ فشل تسجيل عملية FIFO: {error}"
                    )

                else:

                    st.success(
                        f"✅ تم تسجيل الصرف بنجاح\n\n"
                        f"الكمية: {quantity:,.2f}\n\n"
                        f"التكلفة: {money(total_cost)}"
                    )

                    st.session_state.fifo_consuming = False
                    st.rerun()

                st.session_state.fifo_consuming = False

        elif quantity > available_quantity:

            st.error(
                "❌ الكمية المطلوبة أكبر من الكمية المتاحة."
            )

        elif available_quantity <= 0:

            st.warning(
                "⚠️ لا توجد كمية متاحة لهذا المنتج."
            )

    # =====================================================
    # 3 - المخزون والطبقات
    # =====================================================

    with tab3:

        st.markdown(
            f"""
            <h3 style="color:{ACCENT_BLUE};">
                📊 طبقات المخزون المتبقية
            </h3>
            <p style="color:{TEXT_SECONDARY};">
                ترتيب الطبقات من الأقدم إلى الأحدث وفق تاريخ الدفعة.
            </p>
            """,
            unsafe_allow_html=True
        )

        st.divider()

        prod_id = st.selectbox(
            "المنتج",
            options=product_ids,
            format_func=lambda x: product_dict[x],
            key="fifo_view_product"
        )

        batches = get_available_batches(prod_id)

        if not batches:

            st.info(
                "📭 لا توجد طبقات مخزون متبقية لهذا المنتج."
            )

        else:

            rows = []

            total_quantity = 0.0
            total_value = 0.0

            for index, batch in enumerate(batches, start=1):

                quantity = float(batch["remaining"])
                unit_cost = float(batch["unit_cost"])
                value = quantity * unit_cost

                total_quantity += quantity
                total_value += value

                rows.append({
                    "الأولوية": index,
                    "رقم الدفعة": batch["id"],
                    "تاريخ الدفعة": batch["batch_date"],
                    "الكمية المتبقية": quantity,
                    "تكلفة الوحدة": unit_cost,
                    "قيمة الطبقة": value,
                    "المرجع": batch.get("reference", "")
                })

            df = pd.DataFrame(rows)

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "الكمية المتبقية": st.column_config.NumberColumn(
                        format="%.2f"
                    ),
                    "تكلفة الوحدة": st.column_config.NumberColumn(
                        format="%.2f"
                    ),
                    "قيمة الطبقة": st.column_config.NumberColumn(
                        format="%.2f"
                    )
                }
            )

            # -------------------------------------------------
            # إجماليات
            # -------------------------------------------------

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "إجمالي الكمية",
                    f"{total_quantity:,.2f}"
                )

            with col2:
                st.metric(
                    "عدد الطبقات",
                    len(batches)
                )

            with col3:
                st.metric(
                    "إجمالي قيمة المخزون",
                    money(total_value)
                )

            # -------------------------------------------------
            # توضيح FIFO
            # -------------------------------------------------

            first_batch = batches[0]

            st.markdown(
                f"""
                <div style="
                    margin-top:1rem;
                    padding:1rem;
                    border-radius:12px;
                    background:rgba(59,130,246,0.10);
                    border:1px solid rgba(59,130,246,0.25);
                    text-align:right;
                ">
                    <strong style="color:{ACCENT_BLUE};">
                        🎯 الدفعة التالية للاستهلاك
                    </strong>
                    <br><br>

                    الدفعة رقم:
                    <strong>{first_batch["id"]}</strong>
                    <br>

                    التاريخ:
                    <strong>{first_batch["batch_date"]}</strong>
                    <br>

                    الكمية:
                    <strong>{float(first_batch["remaining"]):,.2f}</strong>
                    <br>

                    تكلفة الوحدة:
                    <strong>{money(first_batch["unit_cost"])}</strong>
                </div>
                """,
                unsafe_allow_html=True
            )
