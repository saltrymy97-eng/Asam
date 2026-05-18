import streamlit as st
import sqlite3
from datetime import date

DB_PATH = "erp.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_account_balance(account_code):
    conn = get_conn()
    query = """
        SELECT COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) AS balance
        FROM journal_lines
        WHERE account_name = ?
    """
    result = conn.execute(query, (account_code,)).fetchone()
    conn.close()
    return result["balance"] if result else 0

def get_all_accounts_by_prefix(prefix):
    conn = get_conn()
    accounts = conn.execute(
        "SELECT code, name, is_debit FROM accounts WHERE code LIKE ? ORDER BY code",
        (prefix + "%",)
    ).fetchall()
    conn.close()
    return accounts

def show():
    st.title("🧾 قيد إغلاق الحسابات")
    st.markdown("إنشاء قيد يومية تلقائي لإغلاق حسابات الإيرادات والمصروفات وترحيل صافي الدخل إلى الأرباح المحتجزة.")

    year = st.number_input("السنة المالية", min_value=2000, max_value=2100, value=date.today().year)

    if st.button("🚀 إنشاء قيد الإغلاق", type="primary"):
        conn = get_conn()

        # التأكد من عدم وجود قيد إغلاق مسبق لنفس السنة
        existing = conn.execute(
            "SELECT id FROM journal_entries WHERE description = ? AND date LIKE ?",
            (f"قيد إغلاق السنة المالية {year}", f"{year}%")
        ).fetchone()
        if existing:
            st.warning(f"يوجد بالفعل قيد إغلاق للسنة {year}.")
            conn.close()
            return

        # جمع أرصدة الإيرادات (4)
        revenue_accounts = get_all_accounts_by_prefix("4")
        total_revenue = 0
        revenue_details = []
        for acc in revenue_accounts:
            balance = get_account_balance(acc["code"])
            # الإيرادات دائنة، الرصيد الدائن = ربح
            amount = -balance if acc["is_debit"] == "credit" else balance
            if amount != 0:
                total_revenue += amount
                revenue_details.append((acc["code"], acc["name"], amount))

        # جمع أرصدة المصروفات (5)
        expense_accounts = get_all_accounts_by_prefix("5")
        total_expense = 0
        expense_details = []
        for acc in expense_accounts:
            balance = get_account_balance(acc["code"])
            # المصروفات مدينة، الرصيد المدين = مصروف
            amount = balance if acc["is_debit"] == "debit" else -balance
            if amount != 0:
                total_expense += amount
                expense_details.append((acc["code"], acc["name"], amount))

        net_income = total_revenue - total_expense

        # إنشاء قيد اليومية
        desc = f"قيد إغلاق السنة المالية {year}"
        date_str = f"{year}-12-31"
        cur = conn.execute(
            "INSERT INTO journal_entries (date, description, reference) VALUES (?, ?, ?)",
            (date_str, desc, f"إغلاق {year}")
        )
        entry_id = cur.lastrowid

        # إقفال الإيرادات (مدين)
        for code, name, amt in revenue_details:
            conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, ?, ?, 0)",
                (entry_id, code, abs(amt))
            )

        # إقفال المصروفات (دائن)
        for code, name, amt in expense_details:
            conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, ?, 0, ?)",
                (entry_id, code, abs(amt))
            )

        # توجيه صافي الدخل إلى الأرباح المحتجزة (نفترض حساب 310 مثلاً)
        retained_earnings_code = "310000"  # يمكنك تغييره حسب شجرة حساباتك
        if net_income > 0:
            # ربح: الأرباح المحتجزة دائنة
            conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, ?, 0, ?)",
                (entry_id, retained_earnings_code, net_income)
            )
        elif net_income < 0:
            # خسارة: الأرباح المحتجزة مدينة
            conn.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (?, ?, ?, 0)",
                (entry_id, retained_earnings_code, -net_income)
            )

        conn.commit()
        conn.close()
        st.success(f"تم إنشاء قيد إغلاق السنة {year} بنجاح! صافي الدخل: {net_income:,.2f}")
        st.rerun()
