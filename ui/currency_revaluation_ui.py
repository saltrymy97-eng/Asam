# ui/currency_revaluation_ui.py – واجهة فروق أسعار الصرف (v2.0)
# ✅ معاينة تأثير التقييم على الصندوق/البنك + سعر الصرف الحالي
import streamlit as st
import pandas as pd
from datetime import date
from services.currency_revaluation_service import (
    get_accounts_with_foreign_currency,
    get_foreign_balance,
    perform_revaluation,
    get_revaluation_history,
    get_treasury_impact_preview,   # ✅ جديد
)
from services.currency_service import get_base_currency, get_exchange_rate

T = "#F8FAFC"
S = "#CBD5E1"
BL = "#3B82F6"
GR = "#10B981"
OR = "#F59E0B"
RD = "#EF4444"
PR = "#8B5CF6"


# ============================================================
# بطاقة معلومات الحساب
# ============================================================
def _render_account_card(currency: str, foreign_bal: float, current_local: float):
    st.markdown(
        f"""
        <div style="
            background: linear-gradient(90deg, rgba(59,130,246,0.12), rgba(139,92,246,0.08));
            border-right: 4px solid {BL};
            border-radius: 10px; padding: 14px 18px; margin: 10px 0;
            text-align: right; direction: rtl;
        ">
            <div style="color:{S}; font-size:0.9rem;">تفاصيل الحساب</div>
            <div style="color:{T}; margin-top:6px; font-size:1.05rem;">
                <b>العملة:</b> <span style="color:{BL};">{currency}</span>
                &nbsp;|&nbsp;
                <b>الرصيد الأجنبي:</b>
                <span style="color:{T};"> {foreign_bal:,.2f}</span>
            </div>
            <div style="color:{T}; margin-top:4px; font-size:1.05rem;">
                <b>القيمة المحلية (تاريخية):</b>
                <span style="color:{OR};"> {current_local:,.2f}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# بطاقة معاينة تأثير التقييم على الصندوق/البنك
# ============================================================
def _render_treasury_impact(preview: dict):
    """عرض تأثير التقييم على الصندوق/البنك"""
    if not preview.get("treasury_linked"):
        st.info("ℹ️ هذا الحساب غير مرتبط بصندوق أو بنك — لن يتأثر رصيد النقدية.")
        return

    icon = "💵" if preview["treasury_type"] == "cash" else "🏦"
    kind = "الصندوق" if preview["treasury_type"] == "cash" else "البنك"
    old_b = preview["treasury_old_balance"]
    new_b = preview["treasury_new_balance"]
    diff = preview["difference"]
    color = GR if diff >= 0 else RD

    st.markdown(
        f"""
        <div style="
            background: rgba(16,185,129,0.08);
            border-right: 5px solid {color};
            border-radius: 10px; padding: 16px 20px; margin: 12px 0;
            text-align: right; direction: rtl;
        ">
            <div style="color:{S}; font-size:0.95rem;">
                {icon} <b>تأثير التقييم على {kind}</b> «{preview['treasury_name']}»
            </div>
            <div style="display:flex; justify-content:flex-end; gap:24px; margin-top:10px;">
                <div>
                    <span style="color:{S};">الرصيد الحالي:</span>
                    <b style="color:{T};"> {old_b:,.2f}</b>
                </div>
                <div style="color:{S};">←</div>
                <div>
                    <span style="color:{S};">بعد التقييم:</span>
                    <b style="color:{color};"> {new_b:,.2f}</b>
                </div>
                <div>
                    <span style="color:{S};">التغيير:</span>
                    <b style="color:{color};"> {diff:+,.2f}</b>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# الواجهة الرئيسية
# ============================================================
def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{T}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {PR};">💱 فروق أسعار الصرف</h1>
        <p style="color:{S}; font-size:1.2rem;">إعادة تقييم الأرصدة بالعملات الأجنبية ومعالجة الفروق</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["🔄 إعادة تقييم", "📋 سجل العمليات"])

    # ============================================================
    # التبويب 1: إعادة التقييم
    # ============================================================
    with tab1:
        st.markdown(f"<h3 style='color:{BL};'>إعادة تقييم الأرصدة بالعملات الأجنبية</h3>",
                    unsafe_allow_html=True)

        accounts = get_accounts_with_foreign_currency()
        if not accounts:
            st.info("ℹ️ لا توجد حسابات لديها معاملات بعملات أجنبية")
        else:
            account_options = {
                f"{a['account_code']} - {a['account_name']}": a
                for a in accounts
            }
            selected_display = st.selectbox(
                "اختر الحساب",
                list(account_options.keys()),
                key="fx_account_sel",
            )

            account_data = account_options[selected_display]
            account_id = account_data['account_id']
            account_name = account_data['account_name']
            currency = account_data['currency_code']

            foreign_bal, current_local = get_foreign_balance(account_id, currency)

            _render_account_card(currency, foreign_bal, current_local)

            if abs(foreign_bal) < 0.001:
                st.warning("⚠️ الرصيد صفر، لا حاجة لإعادة التقييم")
            else:
                # ✅ اقتراح سعر الصرف الحالي إن وُجد
                base = get_base_currency()
                base_code = base['code'] if base else 'YER'
                suggested_rate = None
                try:
                    r = get_exchange_rate(currency, base_code)
                    if r:
                        suggested_rate = float(r)
                except Exception:
                    pass

                # القيمة الافتراضية
                default_rate = suggested_rate if suggested_rate else 1.0

                col_rate, col_date = st.columns([2, 2])
                with col_rate:
                    new_rate = st.number_input(
                        "سعر الصرف الجديد",
                        min_value=0.0001,
                        value=float(default_rate),
                        step=0.01,
                        format="%.4f",
                        key="fx_new_rate",
                    )
                    if suggested_rate and abs(suggested_rate - new_rate) > 0.0001:
                        st.caption(
                            f"💡 سعر الصرف الحالي في النظام: "
                            f"**{suggested_rate:,.4f}**"
                        )

                with col_date:
                    rev_date = st.date_input(
                        "تاريخ إعادة التقييم",
                        value=date.today(),
                        key="fx_rev_date",
                    )

                # ✅ معاينة التأثير
                preview = get_treasury_impact_preview(
                    account_id, currency, new_rate
                )

                if preview.get("error"):
                    st.error(f"❌ {preview['error']}")
                else:
                    new_local = preview["new_local_value"]
                    diff = preview["difference"]

                    c1, c2, c3 = st.columns(3)
                    c1.metric("القيمة الجديدة", f"{new_local:,.2f}")
                    c2.metric(
                        "الفرق",
                        f"{diff:+,.2f}",
                        delta=f"{diff:+,.2f}" if abs(diff) > 0.01 else None,
                    )
                    if abs(diff) >= 0.01:
                        kind = "🟢 ربح فروق عملة" if diff > 0 else "🔴 خسارة فروق عملة"
                        c3.metric("الحالة", kind)

                    # ✅ تأثير التقييم على الصندوق/البنك
                    _render_treasury_impact(preview)

                    if abs(diff) < 0.01:
                        st.info("ℹ️ لا يوجد فرق جوهري — لن يتم إنشاء قيد")
                    else:
                        st.markdown("---")

                        if st.button(
                            "💾 تنفيذ إعادة التقييم",
                            type="primary",
                            key="do_revaluation",
                        ):
                            username = st.session_state.get(
                                'user', {}
                            ).get('username', 'admin')

                            with st.spinner("جاري إنشاء قيد إعادة التقييم..."):
                                entry_id, err = perform_revaluation(
                                    account_id, currency, new_rate,
                                    rev_date.strftime("%Y-%m-%d"),
                                    created_by=username,
                                )

                            if err:
                                st.error(f"❌ فشل: {err}")
                            else:
                                st.success(
                                    f"✅ تم إنشاء قيد إعادة التقييم رقم "
                                    f"**#{entry_id}** بنجاح"
                                )
                                if preview.get("treasury_linked"):
                                    st.info(
                                        f"💡 تم تحديث رصيد "
                                        f"{'الصندوق' if preview['treasury_type'] == 'cash' else 'البنك'} "
                                        f"«{preview['treasury_name']}» تلقائياً"
                                    )
                                st.balloons()

    # ============================================================
    # التبويب 2: سجل العمليات
    # ============================================================
    with tab2:
        st.markdown(f"<h3 style='color:{PR};'>سجل عمليات إعادة التقييم</h3>",
                    unsafe_allow_html=True)

        history = get_revaluation_history()
        if not history:
            st.info("لا توجد عمليات سابقة")
        else:
            df = pd.DataFrame(history)

            # ملخص
            total_profit = df[df['difference'] > 0]['difference'].sum()
            total_loss = abs(df[df['difference'] < 0]['difference'].sum())
            c1, c2, c3 = st.columns(3)
            c1.metric("عدد العمليات", len(df))
            c2.metric("إجمالي الأرباح", f"{total_profit:,.2f}")
            c3.metric("إجمالي الخسائر", f"{total_loss:,.2f}")

            st.markdown("---")

            # تجهيز العرض
            df_display = df.copy()
            if 'difference' in df_display.columns:
                df_display['النوع'] = df_display['difference'].apply(
                    lambda x: "🟢 ربح" if float(x) > 0 else "🔴 خسارة"
                )

            df_display = df_display.rename(columns={
                'id': 'الرقم',
                'date': 'التاريخ',
                'account_name': 'الحساب',
                'currency_code': 'العملة',
                'new_rate': 'السعر الجديد',
                'foreign_balance': 'الرصيد الأجنبي',
                'old_local_value': 'قيمة قديمة',
                'new_local_value': 'قيمة جديدة',
                'difference': 'الفرق',
                'journal_entry_id': 'رقم القيد',
                'created_by': 'بواسطة',
            })

            cols = ['الرقم', 'التاريخ', 'الحساب', 'العملة',
                    'السعر الجديد', 'الرصيد الأجنبي',
                    'قيمة قديمة', 'قيمة جديدة', 'الفرق',
                    'النوع', 'رقم القيد']
            cols = [c for c in cols if c in df_display.columns]

            st.dataframe(
                df_display[cols],
                use_container_width=True,
                hide_index=True,
            )
