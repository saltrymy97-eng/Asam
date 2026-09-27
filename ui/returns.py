# ui/returns.py – واجهة مرتجعات البضاعة (v3.0)
# ✅ 3 طرق استرداد: حساب / صندوق / بنك
# ✅ عرض الكميات المباعة/المرجعة/المتبقية
# ✅ فحص فوري للرصيد
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
from services.bank_service import get_all_bank_accounts


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
    """عرض بنود الفاتورة مع الكميات، وإرجاع قائمة المنتجات المختارة"""
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
# ✅ مساعد: خيارات الاسترداد (حساب / نقدي / بنكي)
# ============================================================
def _render_refund_options(prefix, total_estimate):
    """
    يعرض 3 خيارات للاسترداد.
    
    Returns:
        (refund_method, cash_account_code, bank_account_code)
        refund_method ∈ {'account', 'cash', 'bank', 'invalid'}
    """
    st.markdown("---")
    h3("طريقة الاسترداد", GR)

    refund_choice = st.radio(
        "كيف يتم إرجاع المبلغ للطرف؟",
        [
            "💼 خصم من الحساب (بدون نقد)",
            "💵 استرداد نقدي من الصندوق",
            "🏦 تحويل بنكي"
        ],
        horizontal=True,
        key=f"{prefix}_refund_method"
    )

    # ============ خصم من الحساب ============
    if "خصم من الحساب" in refund_choice:
        st.info(f"📌 سيتم خصم **{total_estimate:,.2f}** من رصيد الطرف")
        return "account", None, None

    # ============ استرداد نقدي ============
    if "استرداد نقدي" in refund_choice:
        cash_accounts = get_all_cash_accounts(active_only=True)
        if not cash_accounts:
            st.error("⚠️ لا يوجد صندوق نشط. أضف صندوقاً أولاً.")
            return "invalid", None, None

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

        if total_estimate > cash_acc["current_balance"]:
            st.error(
                f"⚠️ **الرصيد غير كافٍ في الصندوق**\n\n"
                f"المتاح: **{cash_acc['current_balance']:,.2f}**\n\n"
                f"المطلوب: **{total_estimate:,.2f}**\n\n"
                f"❌ لن تتم العملية"
            )
            return "invalid", None, None

        return "cash", cash_acc["account_code"], None

    # ============ تحويل بنكي ============
    if "تحويل بنكي" in refund_choice:
        bank_accounts = get_all_bank_accounts(active_only=True)
        if not bank_accounts:
            st.error("⚠️ لا يوجد حساب بنكي نشط. أضف حساباً بنكياً أولاً.")
            return "invalid", None, None

        bank_labels = [
            f"{ba['bank_name']} ({ba['account_number']}) - {ba['currency_code']} — الرصيد: {ba['current_balance']:,.2f}"
            for ba in bank_accounts
        ]
        selected = st.selectbox(
            "🏦 من أي حساب بنكي سيتم الاسترداد؟",
            bank_labels,
            key=f"{prefix}_bank_sel"
        )
        idx = bank_labels.index(selected)
        bank_acc = bank_accounts[idx]

        if total_estimate > bank_acc["current_balance"]:
            st.error(
                f"⚠️ **الرصيد غير كافٍ في البنك**\n\n"
                f"المتاح: **{bank_acc['current_balance']:,.2f}**\n\n"
                f"المطلوب: **{total_estimate:,.2f}**\n\n"
                f"❌ لن تتم العملية"
            )
            return "invalid", None, None

        return "bank", None, bank_acc["account_code"]

    return "invalid", None, None


# ============================================================
# مساعد: نموذج مرتجع كامل (مبيعات/مشتريات)
# ============================================================
def _render_return_form(invoice_type, inv, items, prefix):
    """
    نموذج موحّد لمرتجع مبيعات أو مشتريات.
    """
    return_items = _render_return_items(items, prefix, inv["id"])

    if not return_items:
        return

    return_date = st.date_input(
        "تاريخ المرتجع",
        value=date.today(),
        key=f"{prefix}_date"
    )
    reason = st.text_area(
        "سبب الإرجاع (اختياري)",
        key=f"{prefix}_reason"
    )

    # حساب تقريبي للإجمالي
    estimate = 0.0
    for name, qty in return_items:
        for it in items:
            if it["name"] == name:
                estimate += qty * float(it["unit_price"])
                break
    estimate = estimate * (1 + float(inv.get("vat_rate") or 0.15))

    refund_method, cash_code, bank_code = _render_refund_options(prefix, estimate)

    st.markdown("---")
    st.markdown(f"**💰 الإجمالي المتوقع للمرتجع:** {estimate:,.2f}")

    # ============ زر التأكيد ============
    session_key = f"saving_{prefix}_return"
    if session_key not in st.session_state:
        st.session_state[session_key] = False

    can_save = (
        not st.session_state[session_key]
        and refund_method != "invalid"
    )

    if st.button(
        f"✅ تأكيد مرتجع {'المبيعات' if invoice_type == 'sale' else 'المشتريات'}",
        key=f"confirm_{prefix}_return",
        type="primary",
        disabled=not can_save
    ):
        st.session_state[session_key] = True
        st.session_state[f"_pending_{prefix}_return"] = {
            "invoice_id": inv["id"],
            "items": return_items,
            "date": return_date.strftime("%Y-%m-%d"),
            "reason": reason,
            "refund_method": refund_method,
            "cash_code": cash_code,
            "bank_code": bank_code,
        }
        st.rerun()

    if st.session_state[session_key]:
        p = st.session_state.get(f"_pending_{prefix}_return")
        if p:
            ok, result, total, note = process_return(
                invoice_type,
                p["invoice_id"],
                p["items"],
                p["date"],
                p["reason"],
                refund_method=p["refund_method"],
                cash_account_code=p["cash_code"],
                bank_account_code=p["bank_code"],
            )
            if ok:
                msg = f"✅ تم تسجيل المرتجع رقم {result} — الإجمالي: {total:,.2f}"
                if note:
                    msg += f"\n\n{note}"
                glass(msg)
            else:
                st.error(f"❌ فشل العملية: {result}")

        st.session_state[session_key] = False
        st.session_state.pop(f"_pending_{prefix}_return", None)
        st.rerun()


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
                    _render_return_form("sale", inv, items, "sret")

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
                    _render_return_form("purchase", inv, items, "pret")

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
