import streamlit as st
import sqlite3
import pandas as pd

DB_PATH = "erp.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_account_balance(account_code):
    """جلب رصيد حساب محدد من جدول journal_lines"""
    conn = get_conn()
    query = """
        SELECT
            COALESCE(SUM(jl.debit), 0) - COALESCE(SUM(jl.credit), 0) AS balance
        FROM journal_lines jl
        WHERE jl.account_name = ?
    """
    result = conn.execute(query, (account_code,)).fetchone()
    conn.close()
    return result["balance"] if result else 0

def get_accounts_by_prefix(prefix):
    """جلب جميع الحسابات المستخدمة في القيود التي تبدأ كوداتها بالبادئة"""
    conn = get_conn()
    # 🆕 يبحث في قيود اليومية مباشرة، مع محاولة جلب الاسم من شجرة الحسابات
    accounts = conn.execute("""
        SELECT DISTINCT jl.account_name as code, 
               COALESCE(a.name, jl.account_name) as name,
               COALESCE(a.is_debit, 
                  CASE 
                    WHEN jl.account_name LIKE '1%' THEN 'debit'
                    WHEN jl.account_name LIKE '5%' THEN 'debit'
                    ELSE 'credit'
                  END) as is_debit
        FROM journal_lines jl
        LEFT JOIN accounts a ON jl.account_name = a.code
        WHERE jl.account_name LIKE ?
        ORDER BY jl.account_name
    """, (prefix + "%",)).fetchall()
    conn.close()
    return accounts

def show():
    st.title("📊 القوائم المالية")

    tab1, tab2 = st.tabs(["📈 قائمة الدخل", "⚖️ الميزانية العمومية"])

    # ========== قائمة الدخل ==========
    with tab1:
        st.subheader("قائمة الدخل")

        # الإيرادات (حسابات تبدأ بـ 4)
        revenue_accounts = get_accounts_by_prefix("4")
        total_revenue = 0
        revenue_data = []
        for acc in revenue_accounts:
            balance = get_account_balance(acc["code"])
            revenue_amount = -balance if acc["is_debit"] == "credit" else balance
            total_revenue += revenue_amount
            revenue_data.append({
                "الكود": acc["code"],
                "الحساب": acc["name"],
                "المبلغ": revenue_amount
            })

        # المصروفات (حسابات تبدأ بـ 5)
        expense_accounts = get_accounts_by_prefix("5")
        total_expenses = 0
        expense_data = []
        for acc in expense_accounts:
            balance = get_account_balance(acc["code"])
            expense_amount = balance if acc["is_debit"] == "debit" else -balance
            total_expenses += expense_amount
            expense_data.append({
                "الكود": acc["code"],
                "الحساب": acc["name"],
                "المبلغ": expense_amount
            })

        net_income = total_revenue - total_expenses

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**الإيرادات**")
            if revenue_data:
                st.dataframe(pd.DataFrame(revenue_data), use_container_width=True, hide_index=True)
                st.markdown(f"**إجمالي الإيرادات: {total_revenue:,.2f}**")
            else:
                st.info("لا توجد إيرادات مسجلة (حسابات تبدأ بـ 4)")

        with col2:
            st.markdown("**المصروفات**")
            if expense_data:
                st.dataframe(pd.DataFrame(expense_data), use_container_width=True, hide_index=True)
                st.markdown(f"**إجمالي المصروفات: {total_expenses:,.2f}**")
            else:
                st.info("لا توجد مصروفات مسجلة (حسابات تبدأ بـ 5)")

        st.markdown("---")
        st.markdown(f"### صافي الدخل: {net_income:,.2f}")
        if net_income >= 0:
            st.success("ربح ✅")
        else:
            st.error("خسارة ⚠️")

    # ========== الميزانية العمومية ==========
    with tab2:
        st.subheader("الميزانية العمومية")

        # الأصول (1)
        asset_accounts = get_accounts_by_prefix("1")
        total_assets = 0
        asset_data = []
        for acc in asset_accounts:
            balance = get_account_balance(acc["code"])
            amount = balance if acc["is_debit"] == "debit" else -balance
            total_assets += amount
            asset_data.append({
                "الكود": acc["code"],
                "الحساب": acc["name"],
                "المبلغ": amount
            })

        # الخصوم (2)
        liability_accounts = get_accounts_by_prefix("2")
        total_liabilities = 0
        liability_data = []
        for acc in liability_accounts:
            balance = get_account_balance(acc["code"])
            amount = -balance if acc["is_debit"] == "credit" else balance
            total_liabilities += amount
            liability_data.append({
                "الكود": acc["code"],
                "الحساب": acc["name"],
                "المبلغ": amount
            })

        # حقوق الملكية (3)
        equity_accounts = get_accounts_by_prefix("3")
        total_equity = 0
        equity_data = []
        for acc in equity_accounts:
            balance = get_account_balance(acc["code"])
            amount = -balance if acc["is_debit"] == "credit" else balance
            total_equity += amount
            equity_data.append({
                "الكود": acc["code"],
                "الحساب": acc["name"],
                "المبلغ": amount
            })

        # نضيف صافي الدخل إلى حقوق الملكية
        rev_total = sum(-get_account_balance(acc["code"]) if acc["is_debit"]=="credit" else get_account_balance(acc["code"]) for acc in get_accounts_by_prefix("4"))
        exp_total = sum(get_account_balance(acc["code"]) if acc["is_debit"]=="debit" else -get_account_balance(acc["code"]) for acc in get_accounts_by_prefix("5"))
        net = rev_total - exp_total
        total_equity += net
        equity_data.append({
            "الكود": "",
            "الحساب": "صافي الدخل (أرباح محتجزة)",
            "المبلغ": net
        })

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**الأصول**")
            if asset_data:
                st.dataframe(pd.DataFrame(asset_data), use_container_width=True, hide_index=True)
                st.markdown(f"**إجمالي الأصول: {total_assets:,.2f}**")
            else:
                st.info("لا توجد أصول مسجلة (حسابات تبدأ بـ 1)")

        with col2:
            st.markdown("**الخصوم وحقوق الملكية**")
            combined = liability_data + equity_data
            if combined:
                st.dataframe(pd.DataFrame(combined), use_container_width=True, hide_index=True)
                st.markdown(f"**إجمالي الخصوم: {total_liabilities:,.2f}**")
                st.markdown(f"**إجمالي حقوق الملكية: {total_equity:,.2f}**")
            else:
                st.info("لا توجد خصوم أو حقوق ملكية مسجلة")

        total_liab_equity = total_liabilities + total_equity

        st.markdown("---")
        col3, col4 = st.columns(2)
        col3.metric("إجمالي الأصول", f"{total_assets:,.2f}")
        col4.metric("إجمالي الخصوم + حقوق الملكية", f"{total_liab_equity:,.2f}")

        if abs(total_assets - total_liab_equity) < 0.01:
            st.success("الميزانية متوازنة ✅")
        else:
            st.error("الميزانية غير متوازنة ⚠️")
