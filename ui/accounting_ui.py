# ui/accounting_ui.py - واجهة الحسابات (تصميم زجاجي فخم + قوائم منسدلة)
import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
from services.accounting_service import (
    get_account_code,
    save_journal_entry,
    get_recent_entries,
    get_entry_details,
    get_ledger,
    get_trial_balance,
    get_distinct_accounts
)
from services.audit_service import log_action

DB_PATH = "erp.db"

# ========== ألوان التصميم ==========
GLASS_BG = "rgba(255, 255, 255, 0.12)"
GLASS_BORDER = "rgba(255, 255, 255, 0.25)"
GLASS_SHADOW = "0 8px 32px 0 rgba(0,0,0,0.37)"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
ACCENT_BLUE = "#3B82F6"
ACCENT_GREEN = "#10B981"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_PURPLE = "#8B5CF6"

def get_accounts_list():
    """جلب جميع الحسابات من شجرة الحسابات"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    accounts = conn.execute("SELECT code, name FROM accounts ORDER BY code").fetchall()
    conn.close()
    return [f"{a['code']} - {a['name']}" for a in accounts]

def show():
    st.markdown(f"""
    <div style="margin-bottom:2rem; text-align:right;">
        <h1 style="color:{TEXT_PRIMARY}; font-size:2.8rem; margin:0; text-shadow:0 0 20px {ACCENT_PURPLE};">🧾 الحسابات</h1>
        <p style="color:{TEXT_SECONDARY}; font-size:1.2rem;">قيود اليومية، دفتر الأستاذ، وميزان المراجعة</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📝 قيود اليومية", "📖 دفتر الأستاذ", "⚖️ ميزان المراجعة"])

    # ---------- قيود اليومية ----------
    with tab1:
        st.markdown(f"<h3 style='color:{ACCENT_BLUE};'>تسجيل قيد يومية</h3>", unsafe_allow_html=True)
        
        # 🆕 جلب قائمة الحسابات مرة واحدة
        accounts_list = get_accounts_list()
        
        if not accounts_list:
            st.warning("لا توجد حسابات. أضف حسابات من شجرة الحسابات أولاً.")
        else:
            with st.form("journal_entry_form"):
                entry_date = st.date_input("التاريخ", value=date.today())
                description = st.text_input("البيان", placeholder="أدخل وصف العملية المالية")
                
                st.markdown(f"<p style='color:{TEXT_SECONDARY}; margin-top:1rem;'>الأسطر المحاسبية (حتى 4 أسطر)</p>", unsafe_allow_html=True)
                
                lines = []
                for i in range(4):
                    cols = st.columns([3, 2, 2])
                    # 🆕 قائمة منسدلة بدلاً من حقل نصي
                    account = cols[0].selectbox(
                        f"الحساب {i+1}",
                        [""] + accounts_list,
                        key=f"acc_{i}"
                    )
                    debit = cols[1].number_input(f"مدين {i+1}", min_value=0.0, step=0.01, key=f"deb_{i}")
                    credit = cols[2].number_input(f"دائن {i+1}", min_value=0.0, step=0.01, key=f"cred_{i}")
                    if account:
                        # استخراج الكود من النص المختار (مثلاً "4 - الإيرادات" → "4")
                        code = account.split(" - ")[0]
                        lines.append({"account": code, "debit": debit, "credit": credit})

                submitted = st.form_submit_button("💾 حفظ القيد", type="primary")
                
                if submitted:
                    if not description:
                        st.error("البيان مطلوب")
                    elif not lines:
                        st.error("أضف سطراً محاسبياً واحداً على الأقل")
                    else:
                        total_debit = sum(l["debit"] for l in lines)
                        total_credit = sum(l["credit"] for l in lines)
                        if abs(total_debit - total_credit) > 0.001:
                            st.error(f"القيد غير متوازن! المدين: {total_debit:,.2f} ، الدائن: {total_credit:,.2f}")
                        else:
                            entry_id, error = save_journal_entry(description, lines, entry_date.strftime("%Y-%m-%d"))
                            if error:
                                st.error(f"فشل في حفظ القيد: {error}")
                            else:
                                log_action(
                                    username=st.session_state.user.get('username', 'admin'),
                                    action="قيد يومية",
                                    table_name="journal_entries",
                                    record_id=entry_id,
                                    new_value=f"البيان: {description}"
                                )
                                st.success("تم تسجيل القيد بنجاح")
                                st.rerun()

        # عرض آخر القيود
        st.markdown("---")
        st.markdown(f"<h4 style='color:{TEXT_PRIMARY};\">آخر قيود اليومية</h4>", unsafe_allow_html=True)
        entries = get_recent_entries()
        if entries:
            df_entries = pd.DataFrame(entries)
            st.dataframe(df_entries, use_container_width=True, hide_index=True)
            
            entry_ids = [e['id'] for e in entries]
            selected_entry = st.selectbox("اختر قيداً لعرض تفاصيله", entry_ids)
            if selected_entry:
                details = get_entry_details(selected_entry)
                if details:
                    df_details = pd.DataFrame(details)
                    st.dataframe(df_details, use_container_width=True, hide_index=True)
                    total_d = sum(d['debit'] for d in details)
                    total_c = sum(d['credit'] for d in details)
                    st.markdown(f"**المجموع: مدين {total_d:,.2f} | دائن {total_c:,.2f}**")
        else:
            st.info("لا توجد قيود بعد")

    # ---------- دفتر الأستاذ ----------
    with tab2:
        st.markdown(f"<h3 style='color:{ACCENT_GREEN};'>دفتر الأستاذ العام</h3>", unsafe_allow_html=True)
        accounts = get_distinct_accounts()
        if accounts:
            selected_account = st.selectbox("اختر الحساب", accounts)
            ledger = get_ledger(selected_account)
            if ledger:
                df_ledger = pd.DataFrame(ledger)
                df_ledger["balance"] = (df_ledger["debit"] - df_ledger["credit"]).cumsum()
                st.dataframe(df_ledger, use_container_width=True, hide_index=True)
                st.markdown(f"**الرصيد النهائي: {df_ledger['balance'].iloc[-1]:,.2f}**")
            else:
                st.info("لا توجد حركات على هذا الحساب")
        else:
            st.info("لا توجد حسابات بعد")

    # ---------- ميزان المراجعة ----------
    with tab3:
        st.markdown(f"<h3 style='color:{ACCENT_ORANGE};'>ميزان المراجعة</h3>", unsafe_allow_html=True)
        tb = get_trial_balance()
        if tb:
            df_tb = pd.DataFrame(tb)
            df_tb["balance"] = df_tb["total_debit"] - df_tb["total_credit"]
            st.dataframe(df_tb, use_container_width=True, hide_index=True)
            total_d = df_tb["total_debit"].sum()
            total_c = df_tb["total_credit"].sum()
            st.markdown(f"**إجمالي المدين: {total_d:,.2f} | إجمالي الدائن: {total_c:,.2f}**")
            if abs(total_d - total_c) < 0.01:
                st.success("الميزان متوازن ✅")
            else:
                st.error("الميزان غير متوازن ⚠️")
        else:
            st.info("لا توجد قيود لعرض ميزان المراجعة")
