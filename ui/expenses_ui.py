# ui/expenses_ui.py – واجهة المصروفات التشغيلية (v2.0)
# ✅ قائمة موحّدة (صناديق + بنوك) + عرض الرصيد + فحص فوري
import streamlit as st
import pandas as pd
from datetime import date
from services.expenses_service import (
    create_expenses_table,
    get_expense_categories,
    get_payment_accounts,       # ✅ جديد
    get_suppliers_for_expense,
    create_expense,
    get_expenses,
)

# ========== ألوان ==========
T = "#F8FAFC"
S = "#CBD5E1"
BL = "#3B82F6"
GR = "#10B981"
OR = "#F59E0B"
RD = "#EF4444"
PR = "#8B5CF6"


def _format_account_label(acc):
    """
    تنسيق عرض الحساب مع الرصيد والنوع.
    """
    icon = "💵" if acc["type"] == "cash" else "🏦"
    return (
        f"{icon} {acc['name']} "
        f"({acc['currency']}) — الرصيد: {acc['balance']:,.2f}"
    )


def show():
    create_expenses_table()

    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{T}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {PR};">🧾 المصروفات التشغيلية</h1>
        <p style="color:{S}; font-size:1.2rem;">تسجيل المصروفات (إيجار، كهرباء، رواتب...) وربطها محاسبياً</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["➕ تسجيل مصروف", "📋 سجل المصروفات"])

    # ============================================================
    # تبويب 1: تسجيل مصروف
    # ============================================================
    with tab1:
        st.markdown(f"<h3 style='color:{GR};'>تسجيل مصروف جديد</h3>",
                    unsafe_allow_html=True)

        categories = get_expense_categories()
        cat_options = [c["code"] for c in categories]
        selected_cat = st.selectbox("نوع المصروف", cat_options)

        col1, col2 = st.columns([1, 1])
        with col1:
            amount = st.number_input("المبلغ", min_value=0.01, step=0.01)
        with col2:
            expense_date = st.date_input("التاريخ", value=date.today())

        # ✅ طرق الدفع الثلاث
        payment_method_label = st.radio(
            "طريقة الدفع",
            ["نقدي (من صندوق)", "بنكي (تحويل)", "آجل (على المورد)"],
            horizontal=True,
            key="expense_payment_method"
        )

        # ============================================================
        # تحديد الحساب + فحص الرصيد
        # ============================================================
        account_code = None
        payment_method = None
        party_type = None
        party_id = None
        balance_ok = True
        selected_acc = None

        # --- نقدي أو بنكي ---
        if "نقدي" in payment_method_label or "بنكي" in payment_method_label:
            all_accounts = get_payment_accounts()

            # فلترة حسب النوع
            if "نقدي" in payment_method_label:
                filtered = [a for a in all_accounts if a["type"] == "cash"]
                if not filtered:
                    st.error("⚠️ لا يوجد صندوق نشط. أضف صندوقاً أولاً.")
                    st.stop()
                payment_method = "cash"
            else:  # بنكي
                filtered = [a for a in all_accounts if a["type"] == "bank"]
                if not filtered:
                    st.error("⚠️ لا يوجد حساب بنكي نشط. أضف حساباً بنكياً أولاً.")
                    st.stop()
                payment_method = "bank"

            # عرض القائمة
            labels = [_format_account_label(a) for a in filtered]
            selected_label = st.selectbox(
                "من أي حساب سيتم الدفع؟",
                labels,
                key="expense_account_sel"
            )
            idx = labels.index(selected_label)
            selected_acc = filtered[idx]
            account_code = selected_acc["code"]

            # ✅ فحص فوري
            if amount > selected_acc["balance"]:
                st.error(
                    f"⚠️ **الرصيد غير كافٍ**\n\n"
                    f"المتاح في **{selected_acc['name']}**: "
                    f"**{selected_acc['balance']:,.2f}** {selected_acc['currency']}\n\n"
                    f"المطلوب: **{amount:,.2f}** {selected_acc['currency']}\n\n"
                    f"❌ لن تتم العملية"
                )
                balance_ok = False
            else:
                st.info(
                    f"✅ الرصيد كافٍ — سيتبقى "
                    f"**{selected_acc['balance'] - amount:,.2f}** {selected_acc['currency']}"
                )

        # --- آجل (على المورد) ---
        else:  # آجل
            payment_method = "credit"
            account_code = ""  # لا حساب

            suppliers = get_suppliers_for_expense()
            if suppliers:
                supplier_options = {s["name"]: s["id"] for s in suppliers}
                selected_supplier_name = st.selectbox(
                    "اختر المورد",
                    list(supplier_options.keys()),
                    key="expense_supplier_sel"
                )
                party_type = "supplier"
                party_id = supplier_options[selected_supplier_name]
            else:
                st.warning("لا يوجد موردون. أضف مورداً أولاً.")
                st.stop()

        # ============================================================
        # حقول إضافية
        # ============================================================
        invoice_ref = st.text_input("رقم فاتورة المورد (اختياري)",
                                     key="expense_invoice_ref")
        notes = st.text_area("ملاحظات", key="expense_notes")

        # ============================================================
        # زر الحفظ
        # ============================================================
        if "saving_expense" not in st.session_state:
            st.session_state.saving_expense = False

        can_save = (
            not st.session_state.saving_expense
            and balance_ok
            and amount > 0
        )

        if st.button(
            "💾 حفظ المصروف",
            type="primary",
            disabled=not can_save,
            key="save_expense_btn"
        ):
            st.session_state.saving_expense = True
            st.rerun()

        if st.session_state.saving_expense:
            try:
                eid, err = create_expense(
                    expense_date.strftime("%Y-%m-%d"),
                    selected_cat,
                    amount,
                    account_code,
                    payment_method,
                    party_type,
                    party_id,
                    invoice_ref,
                    notes,
                    st.session_state.user.get('username', 'admin')
                )
                if err:
                    st.error(f"❌ فشل: {err}")
                else:
                    st.success(f"✅ تم تسجيل المصروف رقم {eid}")
            except Exception as e:
                st.error(f"❌ خطأ غير متوقع: {e}")
            finally:
                st.session_state.saving_expense = False
                st.rerun()

    # ============================================================
    # تبويب 2: سجل المصروفات
    # ============================================================
    with tab2:
        st.markdown(f"<h3 style='color:{PR};'>سجل المصروفات</h3>",
                    unsafe_allow_html=True)

        expenses = get_expenses()

        if expenses:
            # ✅ عرض الإجمالي
            total = sum(float(e.get('amount', 0)) for e in expenses)
            st.markdown(
                f"<div style='background:rgba(16,185,129,0.15); "
                f"padding:0.75rem; border-radius:8px; text-align:right; "
                f"color:{T};'>"
                f"💰 **إجمالي المصروفات:** {total:,.2f}"
                f"</div>",
                unsafe_allow_html=True
            )

            df = pd.DataFrame(expenses)

            method_labels = {
                "cash": "💵 نقدي",
                "bank": "🏦 بنكي",
                "credit": "📌 آجل",
            }
            df["payment_method"] = df["payment_method"].apply(
                lambda x: method_labels.get(x, x)
            )

            df_display = df.rename(columns={
                "id": "الرقم",
                "date": "التاريخ",
                "category": "النوع",
                "amount": "المبلغ",
                "account_code": "الحساب",
                "payment_method": "طريقة الدفع",
                "party_name": "المورد",
                "invoice_ref": "رقم الفاتورة",
                "notes": "ملاحظات",
            })

            cols = ["الرقم", "التاريخ", "النوع", "المبلغ",
                    "طريقة الدفع", "الحساب", "المورد",
                    "رقم الفاتورة", "ملاحظات"]
            cols = [c for c in cols if c in df_display.columns]

            st.dataframe(df_display[cols], use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد مصروفات مسجلة بعد")
