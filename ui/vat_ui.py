# ui/vat_ui.py – واجهة إدارة ضريبة القيمة المضافة (v3.0)
# ✅ تبويب دفع الضريبة + سجل المدفوعات مع الملاحظات
import streamlit as st
from datetime import date
import pandas as pd
from services.vat_service import (
    create_vat_table,
    get_vat_rate,
    update_vat_rate,
    calculate_vat,
    calculate_reverse_vat,
    get_vat_report,
    get_tax_return_report,
    get_vat_history,
    pay_vat,
)
from services.expenses_service import get_payment_accounts
from database import get_connection, close_connection


# ========== ألوان ==========
T = "#F8FAFC"
S = "#CBD5E1"
BL = "#3B82F6"
GR = "#10B981"
OR = "#F59E0B"
RD = "#EF4444"
PR = "#8B5CF6"
CY = "#06B6D4"


def h1(title, color=PR):
    st.markdown(f"""<div style="text-align:right;margin-bottom:2rem;">
        <h1 style="color:{T};font-size:2.8rem;margin:0;text-shadow:0 0 20px {color};">{title}</h1>
        <p style="color:{S};font-size:1.2rem;">إدارة ضريبة القيمة المضافة والتقارير</p>
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


def kpi_card(icon, title, value, color):
    return f"""<div style="background:rgba(255,255,255,0.10);backdrop-filter:blur(12px);
        border:1px solid rgba(255,255,255,0.20);border-radius:16px;padding:1.2rem;
        text-align:center;box-shadow:0 8px 32px rgba(0,0,0,0.37);margin-bottom:0.8rem;">
        <div style="font-size:2rem;margin-bottom:0.3rem;">{icon}</div>
        <div style="color:{S};font-size:0.8rem;">{title}</div>
        <div style="color:{color};font-size:1.6rem;font-weight:800;">{value}</div>
    </div>"""


def _format_account_label(acc):
    """تنسيق عرض الحساب مع الرصيد والنوع"""
    icon = "💵" if acc["type"] == "cash" else "🏦"
    return (
        f"{icon} {acc['name']} ({acc['currency']}) — "
        f"الرصيد: {acc['balance']:,.2f}"
    )


# ============================================================
# جلب سجل مدفوعات الضريبة
# ============================================================
def _get_vat_payments(limit=50):
    """جلب سجل مدفوعات الضريبة من جدول vouchers"""
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT 
                v.id,
                v.date,
                v.amount,
                v.account,
                v.reference,
                v.notes,
                v.created_by,
                v.created_at,
                je.description AS entry_description,
                CASE 
                    WHEN ba.id IS NOT NULL THEN ba.bank_name
                    WHEN ca.id IS NOT NULL THEN ca.name
                    ELSE v.account
                END AS payment_source,
                CASE
                    WHEN ba.id IS NOT NULL THEN 'bank'
                    WHEN ca.id IS NOT NULL THEN 'cash'
                    ELSE 'other'
                END AS source_type
            FROM vouchers v
            LEFT JOIN journal_entries je ON v.journal_entry_id = je.id
            LEFT JOIN bank_accounts ba ON ba.account_code = v.account AND ba.is_active = 1
            LEFT JOIN cash_accounts ca ON ca.account_code = v.account AND ca.is_active = 1
            WHERE v.type = 'payment'
              AND v.party_type = 'tax_authority'
            ORDER BY v.id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Error fetching VAT payments: {e}")
        return []
    finally:
        close_connection(conn)


def show():
    create_vat_table()
    h1("🧾 ضريبة القيمة المضافة (VAT)")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "⚙️ الإعدادات",
        "🧮 حاسبة الضريبة",
        "🔄 الضريبة العكسية",
        "💳 دفع الضريبة",
        "📊 التقارير",
    ])

    # ============================================================
    # تبويب 1: الإعدادات
    # ============================================================
    with tab1:
        h3("إعدادات الضريبة", BL)
        current_rate = get_vat_rate()

        col1, col2 = st.columns(2)
        with col1:
            glass(
                f'النسبة الحالية: '
                f'<span style="color:{GR};font-weight:800;">{current_rate * 100:.0f}%</span>'
            )
        with col2:
            new_rate = st.number_input(
                "تحديث النسبة (%)",
                min_value=0.0, max_value=100.0,
                value=current_rate * 100, step=0.5
            ) / 100
            if st.button("💾 تحديث النسبة", type="primary"):
                update_vat_rate(new_rate)
                st.success(f"✅ تم تحديث نسبة الضريبة إلى {new_rate * 100:.0f}%")
                st.rerun()

        st.markdown("---")
        h3("سجل التغييرات", PR)
        history = get_vat_history()
        if history:
            df = pd.DataFrame(history)
            if 'name' not in df.columns:
                df['name'] = 'ضريبة القيمة المضافة'
            df = df.rename(columns={
                "name": "الاسم", "rate": "النسبة",
                "is_active": "نشط", "created_at": "التاريخ"
            })
            df["النسبة"] = df["النسبة"].apply(lambda x: f"{x * 100:.0f}%")
            df["نشط"] = df["نشط"].apply(lambda x: "✅" if x else "❌")
            cols_to_show = [c for c in ["الاسم", "النسبة", "نشط", "التاريخ"] if c in df.columns]
            st.dataframe(df[cols_to_show], use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد تغييرات سابقة")

    # ============================================================
    # تبويب 2: حاسبة الضريبة
    # ============================================================
    with tab2:
        h3("حساب الضريبة على مبلغ", CY)
        amount = st.number_input("المبلغ (قبل الضريبة)", min_value=0.0, step=100.0)
        if st.button("🧮 احسب الضريبة"):
            vat_amount = calculate_vat(amount)
            total = amount + vat_amount
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(kpi_card("💰", "المبلغ الأساسي", f"{amount:,.2f}", BL),
                            unsafe_allow_html=True)
            with col2:
                st.markdown(kpi_card("🧾", "قيمة الضريبة", f"{vat_amount:,.2f}", OR),
                            unsafe_allow_html=True)
            with col3:
                st.markdown(kpi_card("💎", "الإجمالي", f"{total:,.2f}", GR),
                            unsafe_allow_html=True)

    # ============================================================
    # تبويب 3: الضريبة العكسية
    # ============================================================
    with tab3:
        h3("الضريبة العكسية", CY)
        total_amount = st.number_input("المبلغ الإجمالي (شامل الضريبة)", min_value=0.0, step=100.0)
        if st.button("🔍 احسب الضريبة العكسية"):
            before_tax, vat_amt = calculate_reverse_vat(total_amount)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(kpi_card("💎", "الإجمالي (شامل الضريبة)", f"{total_amount:,.2f}", BL),
                            unsafe_allow_html=True)
            with col2:
                st.markdown(kpi_card("📋", "المبلغ قبل الضريبة", f"{before_tax:,.2f}", GR),
                            unsafe_allow_html=True)
            with col3:
                st.markdown(kpi_card("🧾", "قيمة الضريبة", f"{vat_amt:,.2f}", OR),
                            unsafe_allow_html=True)

    # ============================================================
    # تبويب 4: دفع الضريبة
    # ============================================================
    with tab4:
        h3("💳 دفع الضريبة لجهة الضرائب", OR)

        # ملخص الضريبة الصافية
        st.markdown("### 📊 ملخص الضريبة المستحقة")

        col_a, col_b = st.columns(2)
        with col_a:
            pay_start = st.date_input(
                "من تاريخ (لفحص المستحقات)",
                value=date.today().replace(day=1),
                key="vat_pay_start"
            )
        with col_b:
            pay_end = st.date_input(
                "إلى تاريخ",
                value=date.today(),
                key="vat_pay_end"
            )

        vat_report = get_vat_report(
            pay_start.strftime("%Y-%m-%d"),
            pay_end.strftime("%Y-%m-%d"),
        )

        net_vat = vat_report.get('net_vat', 0)

        if net_vat > 0:
            st.warning(
                f"⚠️ **ضريبة مستحقة الدفع:** {net_vat:,.2f}\n\n"
                f"ضريبة المخرجات: {vat_report.get('output_vat', 0):,.2f}\n\n"
                f"ضريبة المدخلات: {vat_report.get('input_vat', 0):,.2f}"
            )
        elif net_vat < 0:
            st.info(f"ℹ️ **رصيد ضريبي دائن:** {abs(net_vat):,.2f} — لا داعي للدفع")
        else:
            st.info("✅ لا يوجد مستحقات ضريبية في الفترة")

        st.markdown("---")

        # نموذج الدفع
        st.markdown("### 📝 تسجيل دفع الضريبة")

        payment_choice = st.radio(
            "من أي حساب سيتم الدفع؟",
            ["بنكي (تحويل)", "نقدي (من صندوق)"],
            horizontal=True,
            key="vat_payment_method"
        )

        all_accounts = get_payment_accounts()

        if "بنكي" in payment_choice:
            filtered = [a for a in all_accounts if a["type"] == "bank"]
            payment_method = "bank"
            if not filtered:
                st.error("⚠️ لا يوجد حساب بنكي نشط.")
                return
        else:
            filtered = [a for a in all_accounts if a["type"] == "cash"]
            payment_method = "cash"
            if not filtered:
                st.error("⚠️ لا يوجد صندوق نشط.")
                return

        labels = [_format_account_label(a) for a in filtered]
        selected_label = st.selectbox(
            "اختر الحساب",
            labels,
            key="vat_account_sel"
        )
        idx = labels.index(selected_label)
        selected_acc = filtered[idx]
        payment_account_code = selected_acc["code"]

        default_amount = max(0.0, float(net_vat))
        amount_to_pay = st.number_input(
            "المبلغ المراد دفعه",
            min_value=0.0,
            step=100.0,
            value=default_amount,
            key="vat_pay_amount"
        )

        pay_date = st.date_input(
            "تاريخ الدفع",
            value=date.today(),
            key="vat_pay_date"
        )

        reference = st.text_input(
            "المرجع (رقم إشعار الدفع)",
            key="vat_pay_reference"
        )

        notes = st.text_area("ملاحظات", key="vat_pay_notes")

        # فحص فوري للرصيد
        balance_ok = True
        if amount_to_pay > 0:
            if amount_to_pay > selected_acc["balance"]:
                st.error(
                    f"⚠️ **الرصيد غير كافٍ**\n\n"
                    f"المتاح في **{selected_acc['name']}**: "
                    f"**{selected_acc['balance']:,.2f}** {selected_acc['currency']}\n\n"
                    f"المطلوب: **{amount_to_pay:,.2f}** {selected_acc['currency']}\n\n"
                    f"❌ لن تتم العملية"
                )
                balance_ok = False
            else:
                st.info(
                    f"✅ الرصيد كافٍ — سيتبقى "
                    f"**{selected_acc['balance'] - amount_to_pay:,.2f}** "
                    f"{selected_acc['currency']}"
                )

        # زر الدفع
        if "saving_vat_payment" not in st.session_state:
            st.session_state.saving_vat_payment = False

        can_save = (
            not st.session_state.saving_vat_payment
            and balance_ok
            and amount_to_pay > 0
        )

        if st.button(
            "💳 تسجيل دفع الضريبة",
            type="primary",
            use_container_width=True,
            disabled=not can_save,
            key="pay_vat_btn"
        ):
            st.session_state.saving_vat_payment = True
            st.rerun()

        if st.session_state.saving_vat_payment:
            try:
                journal_id, err = pay_vat(
                    amount=amount_to_pay,
                    payment_date=pay_date.strftime("%Y-%m-%d"),
                    payment_account_code=payment_account_code,
                    payment_method=payment_method,
                    reference=reference,
                    notes=notes,
                    created_by=st.session_state.user.get('username', 'admin'),
                )
                if err:
                    st.error(f"❌ فشل: {err}")
                else:
                    st.success(
                        f"✅ تم تسجيل دفع الضريبة بنجاح — "
                        f"رقم القيد: {journal_id}"
                    )
            except Exception as e:
                st.error(f"❌ خطأ غير متوقع: {e}")
            finally:
                st.session_state.saving_vat_payment = False
                st.rerun()

        # ============================================================
        # سجل المدفوعات
        # ============================================================
        st.markdown("---")
        st.markdown("### 📋 سجل مدفوعات الضريبة")

        payments = _get_vat_payments(limit=100)

        if payments:
            df_pay = pd.DataFrame(payments)

            df_pay["source_icon"] = df_pay["source_type"].apply(
                lambda x: "💵" if x == "cash" else ("🏦" if x == "bank" else "📌")
            )
            df_pay["المصدر"] = df_pay["source_icon"] + " " + df_pay["payment_source"].fillna("—")
            df_pay["النوع"] = df_pay["source_type"].apply(
                lambda x: "نقدي" if x == "cash" else ("بنكي" if x == "bank" else "أخرى")
            )

            df_display = df_pay.rename(columns={
                "id": "الرقم",
                "date": "التاريخ",
                "amount": "المبلغ",
                "reference": "المرجع",
                "notes": "الملاحظات",
                "created_by": "بواسطة",
            })

            total_paid = df_pay["amount"].sum()
            st.markdown(
                f"<div style='background:rgba(16,185,129,0.15); "
                f"padding:0.75rem; border-radius:8px; text-align:right; "
                f"color:{T};'>"
                f"💰 **إجمالي المدفوعات:** {total_paid:,.2f} "
                f"| **عدد الدفعات:** {len(payments)}"
                f"</div>",
                unsafe_allow_html=True
            )

            cols = ["الرقم", "التاريخ", "المبلغ", "النوع",
                    "المصدر", "المرجع", "الملاحظات", "بواسطة"]
            cols = [c for c in cols if c in df_display.columns]

            st.dataframe(
                df_display[cols],
                use_container_width=True,
                hide_index=True
            )

            # عرض الملاحظات التفصيلية
            notes_payments = df_pay[
                df_pay["notes"].notna() & (df_pay["notes"] != "")
            ]
            if not notes_payments.empty:
                with st.expander(f"📝 عرض الملاحظات التفصيلية ({len(notes_payments)} دفعة)"):
                    for _, row in notes_payments.iterrows():
                        st.markdown(f"""
                        <div style="background:rgba(255,255,255,0.05);
                                    border-right:3px solid {CY};
                                    border-radius:8px; padding:10px 15px;
                                    margin:8px 0; text-align:right;">
                            <div style="color:{S}; font-size:0.85rem;">
                                💳 دفعة #{row['id']} — {row['date']}
                            </div>
                            <div style="color:{T}; margin-top:5px;">
                                <b>المبلغ:</b> {row['amount']:,.2f} |
                                <b>المرجع:</b> {row['reference'] or '—'}
                            </div>
                            <div style="color:{CY}; margin-top:8px; font-size:1rem;">
                                📝 {row['notes']}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
        else:
            st.info("لا توجد مدفوعات ضريبية مسجلة بعد")

    # ============================================================
    # تبويب 5: التقارير
    # ============================================================
    with tab5:
        h3("تقارير الضريبة", PR)
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("من تاريخ", value=date.today().replace(day=1))
        with col2:
            end_date = st.date_input("إلى تاريخ", value=date.today())

        colA, colB = st.columns(2)
        with colA:
            if st.button("📊 عرض تقرير الملخص"):
                report = get_vat_report(
                    start_date.strftime("%Y-%m-%d") if start_date else None,
                    end_date.strftime("%Y-%m-%d") if end_date else None,
                )
                glass(
                    f'نسبة الضريبة المعتمدة: '
                    f'<span style="color:{GR};font-weight:800;">'
                    f'{report["rate"] * 100:.0f}%</span>'
                )
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.markdown(kpi_card("🛒", "إجمالي المبيعات",
                                          f"{report['total_sales']:,.2f}", BL),
                                unsafe_allow_html=True)
                with col2:
                    st.markdown(kpi_card("📤", "ضريبة المخرجات",
                                          f"{report['output_vat']:,.2f}", RD),
                                unsafe_allow_html=True)
                with col3:
                    st.markdown(kpi_card("📥", "ضريبة المدخلات",
                                          f"{report['input_vat']:,.2f}", OR),
                                unsafe_allow_html=True)
                with col4:
                    st.markdown(kpi_card("💎", "صافي الضريبة",
                                          f"{report['net_vat']:,.2f}", GR),
                                unsafe_allow_html=True)

        with colB:
            if st.button("📋 عرض تقرير الإقرار الضريبي"):
                tax_return = get_tax_return_report(
                    start_date.strftime("%Y-%m-%d") if start_date else None,
                    end_date.strftime("%Y-%m-%d") if end_date else None,
                )
                glass(
                    f'نسبة الضريبة المعتمدة: '
                    f'<span style="color:{GR};font-weight:800;">'
                    f'{tax_return["rate"] * 100:.0f}%</span>'
                )
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(kpi_card("📤", "إجمالي ضريبة المخرجات",
                                          f"{tax_return['total_output_vat']:,.2f}", RD),
                                unsafe_allow_html=True)
                with col2:
                    st.markdown(kpi_card("📥", "إجمالي ضريبة المدخلات",
                                          f"{tax_return['total_input_vat']:,.2f}", OR),
                                unsafe_allow_html=True)
                with col3:
                    st.markdown(kpi_card("💎", "صافي الضريبة المستحقة",
                                          f"{tax_return['net_vat']:,.2f}", GR),
                                unsafe_allow_html=True)

                if tax_return["invoices"]:
                    st.markdown("---")
                    st.markdown("**📋 تفاصيل الفواتير**")
                    df_inv = pd.DataFrame(tax_return["invoices"])
                    df_inv = df_inv.rename(columns={
                        "id": "رقم الفاتورة", "type": "النوع",
                        "invoice_date": "التاريخ", "total": "الإجمالي",
                        "vat_amount": "الضريبة", "vat_rate": "النسبة",
                    })
                    df_inv["النوع"] = df_inv["النوع"].apply(
                        lambda x: "بيع" if x == "sale" else "شراء"
                    )
                    df_inv["النسبة"] = df_inv["النسبة"].apply(lambda x: f"{x*100:.0f}%")
                    st.dataframe(
                        df_inv[["رقم الفاتورة", "النوع", "التاريخ",
                                "الإجمالي", "الضريبة", "النسبة"]],
                        use_container_width=True, hide_index=True
                    )
                else:
                    st.info("لا توجد فواتير في الفترة المحددة.")
