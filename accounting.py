# modules/accounting.py - الحسابات وقيود اليومية
import streamlit as st
import pandas as pd
from database import get_connection

def show():
    st.title("🧾 الحسابات")
    conn = get_connection()

    tab1, tab2, tab3 = st.tabs(["قيود اليومية", "دفتر الأستاذ", "ميزان المراجعة"])

    # ---------- تبويب قيود اليومية ----------
    with tab1:
        st.subheader("تسجيل قيد يومية")

        with st.form("journal_entry_form"):
            date = st.date_input("التاريخ")
            description = st.text_input("البيان")
            reference = st.text_input("المرجع (اختياري)")

            st.markdown("**الأسطر المحاسبية**")
            # سنسمح بإضافة حتى 4 أسطر في هذا المثال
            lines = []
            for i in range(4):
                cols = st.columns([3, 2, 2])
                account = cols[0].text_input(f"الحساب {i+1}", key=f"acc_{i}")
                debit = cols[1].number_input(f"مدين {i+1}", min_value=0.0, step=0.01, key=f"deb_{i}")
                credit = cols[2].number_input(f"دائن {i+1}", min_value=0.0, step=0.01, key=f"cred_{i}")
                if account:
                    lines.append({"account": account, "debit": debit, "credit": credit})

            submitted = st.form_submit_button("حفظ القيد")
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
                        try:
                            cur = conn.execute(
                                "INSERT INTO journal_entries (date, description, reference) VALUES (?, ?, ?)",
                                (date.strftime("%Y-%m-%d"), description, reference)
                            )
                            entry_id = cur.lastrowid
                            for line in lines:
                                conn.execute(
                                    "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, ?, ?, ?)",
                                    (entry_id, line["account"], line["debit"], line["credit"])
                                )
                            conn.commit()
                            st.success("تم تسجيل القيد بنجاح")
                            st.rerun()
                        except Exception as e:
                            st.error(f"فشل في حفظ القيد: {e}")

        # عرض آخر القيود
        st.markdown("---")
        st.subheader("آخر قيود اليومية")
        entries = pd.read_sql_query(
            "SELECT id, date, description, reference FROM journal_entries ORDER BY id DESC LIMIT 10",
            conn
        )
        if not entries.empty:
            selected_entry = st.selectbox("اختر قيداً لعرض تفاصيله", entries["id"].tolist())
            details = pd.read_sql_query(
                "SELECT account_name, debit, credit FROM journal_lines WHERE entry_id = ?",
                conn, params=(selected_entry,)
            )
            st.dataframe(details, use_container_width=True)
            st.markdown(f"**المجموع: مدين {details['debit'].sum():,.2f} | دائن {details['credit'].sum():,.2f}**")
            st.dataframe(entries, use_container_width=True)
        else:
            st.info("لا توجد قيود بعد")

    # ---------- تبويب دفتر الأستاذ ----------
    with tab2:
        st.subheader("دفتر الأستاذ العام")
        accounts = pd.read_sql_query(
            "SELECT DISTINCT account_name FROM journal_lines ORDER BY account_name",
            conn
        )
        if not accounts.empty:
            selected_account = st.selectbox("اختر الحساب", accounts["account_name"].tolist())
            ledger = pd.read_sql_query(
                """SELECT je.date, je.description, jl.debit, jl.credit
                   FROM journal_lines jl
                   JOIN journal_entries je ON jl.entry_id = je.id
                   WHERE jl.account_name = ?
                   ORDER BY je.date, je.id""",
                conn, params=(selected_account,)
            )
            if not ledger.empty:
                # حساب الرصيد التراكمي (مدين - دائن)
                ledger["balance"] = (ledger["debit"] - ledger["credit"]).cumsum()
                st.dataframe(ledger, use_container_width=True)
                st.markdown(f"**الرصيد النهائي: {ledger['balance'].iloc[-1]:,.2f}**")
            else:
                st.info("لا توجد حركات على هذا الحساب")
        else:
            st.info("لا توجد حسابات بعد")

    # ---------- تبويب ميزان المراجعة ----------
    with tab3:
        st.subheader("ميزان المراجعة")
        trial_balance = pd.read_sql_query(
            """SELECT account_name,
                      SUM(debit) as total_debit,
                      SUM(credit) as total_credit
               FROM journal_lines
               GROUP BY account_name
               ORDER BY account_name""",
            conn
        )
        if not trial_balance.empty:
            trial_balance["balance"] = trial_balance["total_debit"] - trial_balance["total_credit"]
            st.dataframe(trial_balance, use_container_width=True)
            total_d = trial_balance["total_debit"].sum()
            total_c = trial_balance["total_credit"].sum()
            st.markdown(f"**إجمالي المدين: {total_d:,.2f} | إجمالي الدائن: {total_c:,.2f}**")
            if abs(total_d - total_c) < 0.01:
                st.success("الميزان متوازن ✅")
            else:
                st.error("الميزان غير متوازن ⚠️")
        else:
            st.info("لا توجد قيود لعرض ميزان المراجعة")

    conn.close()
