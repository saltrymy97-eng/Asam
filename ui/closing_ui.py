# ui/closing_ui.py – واجهة قيد إغلاق الحسابات (v2.0)
# ✅ حالة السنة + تأكيد + عرض الملخص + إغلاق مركز التكلفة
import streamlit as st
import pandas as pd
from datetime import date
from services.closing_service import (
    create_closing_entry,
    create_cost_center_closing_entry,
    get_closing_summary,
)
from services import cost_center_service as ccs

# ========== ألوان ==========
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_RED = "#EF4444"
ACCENT_ORANGE = "#F59E0B"
ACCENT_PURPLE = "#8B5CF6"


# ============================================================
# بطاقة حالة الإغلاق
# ============================================================
def _render_status_card(summary: dict):
    """عرض بطاقة حالة السنة المالية"""
    if summary.get("error"):
        st.error(summary["error"])
        return

    year = summary.get("year", "—")
    closed = summary.get("closed", False)

    if closed:
        color = ACCENT_GREEN
        icon = "✅"
        status = f"مُغلقة في {summary.get('closed_at', '—')} بواسطة {summary.get('closed_by', '—')}"
    else:
        color = ACCENT_ORANGE
        icon = "⚠️"
        status = "غير مُغلقة بعد"

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(90deg, rgba(59,130,246,0.12), rgba(139,92,246,0.08));
            border-right: 5px solid {color};
            border-radius: 10px; padding: 16px 20px; margin: 10px 0;
            text-align: right; direction: rtl;
        ">
            <div style="color:{TEXT_SECONDARY}; font-size:0.95rem;">حالة السنة المالية {year}</div>
            <div style="color:{color}; font-size:1.4rem; font-weight:bold;">
                {icon} {status}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# بطاقة ملخص السيولة (صندوق + بنك)
# ============================================================
def _render_liquidity_card(summary: dict):
    """عرض ملخص أرصدة الصندوق والبنك"""
    cash_total = summary.get("cash_total", 0.0)
    bank_total = summary.get("bank_total", 0.0)
    liquidity = summary.get("liquidity_total", 0.0)

    c1, c2, c3 = st.columns(3)
    c1.metric("💵 إجمالي الصناديق", f"{cash_total:,.2f}")
    c2.metric("🏦 إجمالي البنوك", f"{bank_total:,.2f}")
    c3.metric("💰 إجمالي السيولة", f"{liquidity:,.2f}")

    # تفاصيل الصناديق
    cash_accounts = summary.get("cash_accounts", [])
    if cash_accounts:
        with st.expander(f"💵 تفاصيل الصناديق ({len(cash_accounts)})", expanded=False):
            df = pd.DataFrame(cash_accounts)
            if "currency_code" in df.columns and "current_balance" in df.columns:
                df.columns = [
                    {"name": "الاسم", "currency_code": "العملة",
                     "current_balance": "الرصيد"}.get(c, c)
                    for c in df.columns
                ]
            st.dataframe(df, use_container_width=True, hide_index=True)

    # تفاصيل البنوك
    bank_accounts = summary.get("bank_accounts", [])
    if bank_accounts:
        with st.expander(f"🏦 تفاصيل البنوك ({len(bank_accounts)})", expanded=False):
            df = pd.DataFrame(bank_accounts)
            if "bank_name" in df.columns:
                rename_map = {
                    "bank_name": "البنك", "account_number": "رقم الحساب",
                    "currency_code": "العملة", "current_balance": "الرصيد",
                }
                df = df.rename(columns=rename_map)
            st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================
# الواجهة الرئيسية
# ============================================================
def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">🧾 قيد إغلاق الحسابات</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">إنشاء قيد تلقائي لإغلاق الإيرادات والمصروفات وترحيل صافي الدخل</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs([
        "🏢 إغلاق الشركة (عام)",
        "🏷️ إغلاق مركز تكلفة"
    ])

    # ============================================================
    # تبويب 1: إغلاق الشركة
    # ============================================================
    with tab1:
        current_year = date.today().year

        col1, col2 = st.columns([2, 3])
        with col1:
            year = st.number_input(
                "السنة المالية",
                min_value=2000,
                max_value=current_year + 1,
                value=current_year,
                step=1,
                key="close_year",
            )
        with col2:
            st.write("")
            st.write("")
            st.caption("⚠️ الإغلاق نهائي — لا يمكن التراجع عنه تلقائياً.")

        # جلب الملخص والحالة
        with st.spinner("جاري فحص حالة السنة..."):
            summary = get_closing_summary(year)

        if summary.get("error"):
            st.error(f"❌ {summary['error']}")
        else:
            _render_status_card(summary)

            # عرض أرصدة السيولة
            st.markdown(f"<h4 style='color:{ACCENT_BLUE};'>💼 ملخص السيولة الحالي</h4>",
                        unsafe_allow_html=True)
            _render_liquidity_card(summary)

            # معلومات إضافية
            st.markdown("---")
            st.markdown(
                f"""
                <div style="
                    background: rgba(59,130,246,0.08);
                    border-right: 4px solid {ACCENT_BLUE};
                    border-radius: 8px; padding: 14px 18px;
                    text-align: right; direction: rtl;
                    color: {TEXT_SECONDARY}; font-size: 0.95rem;
                ">
                <b style="color:{TEXT_PRIMARY};">ما يفعله قيد الإغلاق:</b><br>
                • تصفير أرصدة حسابات الإيرادات (4xxx) في الأرباح المحتجزة<br>
                • تصفير أرصدة حسابات المصروفات (5xxx) في الأرباح المحتجزة<br>
                • ترحيل صافي الدخل (ربح/خسارة) إلى حساب الأرباح المحتجزة<br>
                • <b style="color:{ACCENT_ORANGE};">لا يمسّ</b> الصناديق أو البنوك أو الأصول
                </div>
                """,
                unsafe_allow_html=True,
            )

            # زر الإغلاق
            if summary.get("closed"):
                st.warning(
                    f"⚠️ السنة {year} مُغلقة مسبقاً في "
                    f"**{summary.get('closed_at', '—')}** "
                    f"بواسطة **{summary.get('closed_by', '—')}**. "
                    f"لا يمكن إغلاقها مرة أخرى."
                )
            else:
                st.markdown("---")
                # تأكيد مزدوج
                if "confirm_close_year" not in st.session_state:
                    st.session_state.confirm_close_year = False

                if not st.session_state.confirm_close_year:
                    if st.button(
                        f"🚀 بدء إغلاق السنة {year}",
                        type="primary",
                        key="start_close_year",
                    ):
                        st.session_state.confirm_close_year = True
                        st.rerun()
                else:
                    st.error(
                        f"⚠️ **تأكيد نهائي:** أنت على وشك إغلاق السنة **{year}** "
                        f"للشركة بالكامل. لا يمكن التراجع!"
                    )
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button(
                            f"✅ نعم، أغلق السنة {year}",
                            type="primary",
                            key="confirm_yes_year",
                        ):
                            username = st.session_state.get(
                                'user', {}
                            ).get('username', 'admin')

                            with st.spinner("جاري إنشاء قيد الإغلاق..."):
                                success, net_income, error = create_closing_entry(
                                    year, username=username
                                )

                            st.session_state.confirm_close_year = False

                            if error:
                                st.error(f"❌ فشل: {error}")
                            elif success:
                                st.success(
                                    f"✅ تم إغلاق السنة {year} بنجاح! "
                                    f"صافي الدخل: **{net_income:,.2f}**"
                                )
                                st.balloons()
                                # لا نعمل rerun فوري — نترك الرسالة تظهر
                    with c2:
                        if st.button(
                            "❌ إلغاء",
                            key="confirm_no_year",
                        ):
                            st.session_state.confirm_close_year = False
                            st.rerun()

    # ============================================================
    # تبويب 2: إغلاق مركز تكلفة
    # ============================================================
    with tab2:
        st.markdown(f"<h4 style='color:{ACCENT_PURPLE};'>🏷️ إغلاق مركز تكلفة محدد</h4>",
                    unsafe_allow_html=True)
        st.caption("تصفير إيرادات ومصروفات مركز تكلفة معين في حساب الأرباح المحتجزة.")

        # جلب المراكز
        try:
            centers = ccs.get_all_cost_centers()
        except Exception:
            centers = []

        if not centers:
            st.info("ℹ️ لا توجد مراكز تكلفة — أنشئ مركزاً أولاً من وحدة مراكز التكلفة.")
        else:
            col1, col2 = st.columns([2, 3])

            with col1:
                center_options = {
                    f"{c.get('code', '')} - {c.get('name', '')}": c
                    for c in centers
                }
                selected_str = st.selectbox(
                    "اختر مركز التكلفة",
                    list(center_options.keys()),
                    key="cc_close_select",
                )
                center = center_options[selected_str]

            with col2:
                center_year = st.number_input(
                    "السنة المالية",
                    min_value=2000,
                    max_value=date.today().year + 1,
                    value=date.today().year,
                    step=1,
                    key="cc_close_year",
                )

            # زر الإغلاق
            st.markdown("---")

            if "confirm_close_cc" not in st.session_state:
                st.session_state.confirm_close_cc = False

            if not st.session_state.confirm_close_cc:
                if st.button(
                    f"🚀 إغلاق مركز «{center.get('name', '')}»",
                    type="primary",
                    key="start_close_cc",
                ):
                    st.session_state.confirm_close_cc = True
                    st.rerun()
            else:
                st.error(
                    f"⚠️ **تأكيد نهائي:** إغلاق مركز "
                    f"**{center.get('name', '')}** للسنة **{center_year}**. "
                    f"لا يمكن التراجع!"
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(
                        "✅ نعم، أغلق المركز",
                        type="primary",
                        key="confirm_yes_cc",
                    ):
                        username = st.session_state.get(
                            'user', {}
                        ).get('username', 'admin')

                        with st.spinner("جاري إنشاء قيد الإغلاق..."):
                            success, net_income, error = create_cost_center_closing_entry(
                                center_year, center['id'], username=username
                            )

                        st.session_state.confirm_close_cc = False

                        if error:
                            st.error(f"❌ فشل: {error}")
                        elif success:
                            st.success(
                                f"✅ تم إغلاق المركز للسنة {center_year} — "
                                f"صافي الدخل: **{net_income:,.2f}**"
                            )
                            st.balloons()
                with c2:
                    if st.button("❌ إلغاء", key="confirm_no_cc"):
                        st.session_state.confirm_close_cc = False
                        st.rerun()
