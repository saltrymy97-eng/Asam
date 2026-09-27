# ui/returns.py – واجهة مرتجعات البضاعة (v2.0)
# ✅ عرض الكميات المباعة/المرجعة/المتبقية لكل فاتورة
# ✅ اختيار طريقة الاسترداد (نقدي / حساب)
# ✅ حماية الرصيد
import streamlit as st
import pandas as pd
from datetime import date
from services.returns_service import (
    get_sales_invoices,
    get_purchase_invoices,
    get_invoice_items,
    process_return,
    get_return_history,
)
from services.cash_service import get_all_cash_accounts


# ========== ألوان التصميم ==========
T = "#F8FAFC"
S = "#CBD5E1"
BL = "#3B82F6"
GR = "#10B981"
OR = "#F59E0B"
RD = "#EF4444"
PR = "#8B5CF6"


def h1(title, color=PR):
    st.markdown(f"""<div style="text-align:right;margin-bottom:2rem;">
        <h1 style="color:{T};font-size:2.8rem;margin:0;text-shadow:0 0 20px {color};">{title}</h1>
        <p style="color:{S};font-size:1.2rem;">إدارة مرتجعات المبيعات والمشتريات</p>
    </div>""", unsafe_allow_html=True)


def h3(title, color=BL):
    st.markdown(f"""<h3 style="color:{color};text-align:right;margin-bottom:1rem;">{title}</h3>""",
                unsafe_allow_html=True)


def glass(content):
    st.markdown(
        f"""<div style="background:rgba(255,255,255,0.12);backdrop-filter:blur(10px);
        border:1px solid rgba(255,255,255,0.25);border-radius:16px;padding:1.5rem;
        margin:1rem 0;box-shadow:0 8px 32px rgba(0,0,0,0.37);color:{T};font-size:1.1rem;">
        {content}</div>""",
        unsafe_allow_html=True
    )


# ============================================================
# مساعد: عرض بنود الفاتورة + اختيار المرتجع
# ============================================================
def _render_return_items(items, prefix, invoice_id):
    """
    يعرض بنود الفاتورة مع الكميات المباعة والمرجعة والمتبقية.
    
    Returns:
        list of (product_name, qty) للبنود المرتجعة
    """
    display_items = []
    for item in items:
        display_items.append({
            "اسم المنتج": item["name"],
            "الكمية المباعة": item["quantity"],
            "المرجع سابقاً": item.get("returned_qty", 0),
            "المتاح للإرجاع": item["available_qty"],
            "سعر الوحدة": f"{item['unit_price']:,.2f}",
        })

    df = pd.DataFrame(display_items)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")
    h3("اختر الكميات المراد إرجاعها", OR)

    return_items = []
    has_available = False

    for item in items:
        available = item["available_qty"]
        if available <= 0:
            continue
        has_available = True

        col1, col2 = st.columns([2, 1])
        with col1:
            st.write(
                f"**{item['name']}** — "
                f"مباع: {item['quantity']}، "
                f"مرجع: {item.get('returned_qty', 0)}، "
                f"**متاح للإرجاع: {available}**"
            )
        with col2:
            qty_str = st.text_input(
                "الكمية",
                value="0",
                key=f"{prefix}_{invoice_id}_{item['id']}",
                label_visibility="collapsed"
            )
            try:
                qty = int(qty_str) if qty_str else 0
            except ValueError:
                qty = 0
            if qty < 0:
                qty = 0
            if qty > available:
                qty = available
                st.warning(f"تم تخفيض الكمية إلى الحد الأقصى {available}")
            if qty > 0:
                return_items.append((item["name"], qty))

    if not has_available:
        st.info("لا توجد كميات متاحة للإرجاع في هذه الفاتورة")

    return return_items


# ============================================================
# مساعد: نموذج المرتجع النقدي/الحسابي
# ============================================================
def _render_refund_options(prefix, invoice_type, total_estimate):
    """
    يعرض خيارات طريقة الاسترداد مع اختيار الصندوق.
    
    Returns:
        (refund_method, cash_account_code)
    """
    st.markdown("---")
    h3("طريقة الاسترداد", GR)

    refund_choice = st.radio(
        "كيف يتم إرجاع المبلغ؟",
        ["خصم من الحساب (بدون نقد)", "استرداد نقدي من الصندوق"],
        horizontal=True,
        key=f"{prefix}_refund_method"
    )

    if refund_choice == "استرداد نقدي من الصندوق":
        cash_accounts = get_all_cash_accounts(active_only=True)
        if not cash_accounts:
            st.error("⚠️ لا يوجد صندوق نشط. أضف صندوقاً أولاً.")
            return "account", None

        cash_labels = [
            f"{ca['name']} ({ca['currency_code']}) — الرصيد: {ca['current_balance']:,.2f}"
            for ca in cash_accounts
        ]
        selected = st.selectbox(
            "💵 من أي صندوق سيتم الاسترداد؟",
            cash_labels,
            key=f"{prefix}_cash_sel"
        )
        idx = cash_labels.index(selected)
        cash_acc = cash_accounts[idx]

        # ✅ فحص فوري
        if total_estimate > cash_acc["current_balance"]:
            st.error(
                f"⚠️ **الرصيد غير كافٍ**\n\n"
                f"المتاح في الصندوق: **{cash_acc['current_balance']:,.2f}**\n\n"
                f"المطلوب إرجاعه: **{total_estimate:,.2f}**\n\n"
                f"❌ لن تتم العملية"
            )
            return "cash", None  # سيُرفض

        return "cash", cash_acc["account_code"]

    return "account", None


# ============================================================
# الصفحة الرئيسية
# ============================================================
def show():
    h1("🔄 مرتجعات البضاعة")

    tab1, tab2, tab3 = st.tabs(["مرتجع مبيعات", "مرتجع مشتريات", "سجل المرتجعات"])

    # ============================================================
    # تبويب 1: مرتجع مبيعات
    # ============================================================
    with tab1:
        h3("إرجاع بضاعة من عميل", GR)
        invoices = get_sales_invoices()

        if not invoices:
            st.info("لا توجد فواتير مبيعات مكتملة")
        else:
            invoice_options = {
                f"فاتورة #{inv['id']} - {inv['customer']} ({inv['invoice_date']})": inv
                for inv in invoices
            }
            selected = st.selectbox(
                "اختر الفاتورة",
                list(invoice_options.keys()),
                key="sales_return_inv"
            )

            if selected:
                inv = invoice_options[selected]
                items = get_invoice_items(inv["id"])

                if items:
                    return_items = _render_return_items(items, "sret", inv["id"])

                    if return_items:
                        return_date = st.date_input("تاريخ المرتجع", value=date.today())
                        reason = st.text_area("سبب الإرجاع (اختياري)")

                        # حساب تقريبي للإجمالي
                        estimate = 0.0
                        for name, qty in return_items:
                            for it in items:
                                if it["name"] == name:
                                    estimate += qty * float(it["unit_price"])
                                    break
                        estimate = estimate * (1 + float(inv.get("vat_rate") or 0.15))

                        refund_method, cash_code = _render_refund_options(
                            "sale", "sale", estimate
                        )

                        # ✅ زر التأكيد
                        if "saving_sale_return" not in st.session_state:
                            st.session_state.saving_sale_return = False

                        can_save = (
                            not st.session_state.saving_sale_return
                            and (refund_method == "account" or cash_code is not None)
                        )

                        if st.button(
                            "✅ تأكيد مرتجع المبيعات",
                            key="confirm_sale_return",
                            type="primary",
                            disabled=not can_save
                        ):
                            st.session_state.saving_sale_return = True
                            st.session_state._pending_sale_return = {
                                "invoice_id": inv["id"],
                                "items": return_items,
                                "date": return_date.strftime("%Y-%m-%d"),
                                "reason": reason,
                                "refund_method": refund_method,
                                "cash_code": cash_code,
                            }
                            st.rerun()

                        if st.session_state.saving_sale_return:
                            p = st.session_state.get("_pending_sale_return")
                            if p:
                                ok, result, total, note = process_return(
                                    "sale",
                                    p["invoice_id"],
                                    p["items"],
                                    p["date"],
                                    p["reason"],
                                    refund_method=p["refund_method"],
                                    cash_account_code=p["cash_code"],
                                )
                                if ok:
                                    msg = f"✅ تم تسجيل المرتجع رقم {result} — الإجمالي: {total:,.2f}"
                                    if note:
                                        msg += f"\n\n{note}"
                                    glass(msg)
                                else:
                                    st.error(f"❌ فشل العملية: {result}")

                            st.session_state.saving_sale_return = False
                            st.session_state.pop("_pending_sale_return", None)
                            st.rerun()

    # ============================================================
    # تبويب 2: مرتجع مشتريات
    # ============================================================
    with tab2:
        h3("إرجاع بضاعة للمورد", BL)
        invoices = get_purchase_invoices()

        if not invoices:
            st.info("لا توجد فواتير مشتريات مكتملة")
        else:
            invoice_options = {
                f"فاتورة #{inv['id']} - {inv['supplier']} ({inv['invoice_date']})": inv
                for inv in invoices
            }
            selected = st.selectbox(
                "اختر الفاتورة",
                list(invoice_options.keys()),
                key="purchase_return_inv"
            )

            if selected:
                inv = invoice_options[selected]
                items = get_invoice_items(inv["id"])

                if items:
                    return_items = _render_return_items(items, "pret", inv["id"])

                    if return_items:
                        return_date = st.date_input("تاريخ المرتجع",
                                                     value=date.today(),
                                                     key="purchase_ret_date")
                        reason = st.text_area("سبب الإرجاع (اختياري)",
                                               key="purchase_ret_reason")

                        # حساب تقريبي
                        estimate = 0.0
                        for name, qty in return_items:
                            for it in items:
                                if it["name"] == name:
                                    estimate += qty * float(it["unit_price"])
                                    break
                        estimate = estimate * (1 + float(inv.get("vat_rate") or 0.15))

                        refund_method, cash_code = _render_refund_options(
                            "purchase", "purchase", estimate
                        )

                        if "saving_purchase_return" not in st.session_state:
                            st.session_state.saving_purchase_return = False

                        can_save = (
                            not st.session_state.saving_purchase_return
                            and (refund_method == "account" or cash_code is not None)
                        )

                        if st.button(
                            "✅ تأكيد مرتجع المشتريات",
                            key="confirm_purchase_return",
                            type="primary",
                            disabled=not can_save
                        ):
                            st.session_state.saving_purchase_return = True
                            st.session_state._pending_purchase_return = {
                                "invoice_id": inv["id"],
                                "items": return_items,
                                "date": return_date.strftime("%Y-%m-%d"),
                                "reason": reason,
                                "refund_method": refund_method,
                                "cash_code": cash_code,
                            }
                            st.rerun()

                        if st.session_state.saving_purchase_return:
                            p = st.session_state.get("_pending_purchase_return")
                            if p:
                                ok, result, total, note = process_return(
                                    "purchase",
                                    p["invoice_id"],
                                    p["items"],
                                    p["date"],
                                    p["reason"],
                                    refund_method=p["refund_method"],
                                    cash_account_code=p["cash_code"],
                                )
                                if ok:
                                    msg = f"✅ تم تسجيل المرتجع رقم {result} — الإجمالي: {total:,.2f}"
                                    if note:
                                        msg += f"\n\n{note}"
                                    glass(msg)
                                else:
                                    st.error(f"❌ فشل العملية: {result}")

                            st.session_state.saving_purchase_return = False
                            st.session_state.pop("_pending_purchase_return", None)
                            st.rerun()

    # ============================================================
    # تبويب 3: سجل المرتجعات
    # ============================================================
    with tab3:
        h3("سجل عمليات المرتجعات", PR)
        returns = get_return_history()
        if returns:
            display_returns = []
            for r in returns:
                type_name = "مرتجع مبيعات" if r['type'] == 'sale_return' else "مرتجع مشتريات"
                display_returns.append({
                    "رقم المرتجع": r['id'],
                    "النوع": type_name,
                    "التاريخ": r['invoice_date'],
                    "الإجمالي": f"{float(r['total'] or 0):,.2f}",
                    "الكمية": r.get('total_qty', 0),
                    "السبب": r.get('reason', '') or '—',
                })
            df = pd.DataFrame(display_returns)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد مرتجعات بعد")
