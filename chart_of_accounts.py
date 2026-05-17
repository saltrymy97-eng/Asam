import streamlit as st
import sqlite3
import pandas as pd

DB_PATH = "erp.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_accounts_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            parent_id INTEGER,
            level INTEGER DEFAULT 1,
            is_debit TEXT DEFAULT 'debit',
            FOREIGN KEY (parent_id) REFERENCES accounts(id)
        )
    """)
    conn.commit()
    conn.close()

def add_account(code, name, parent_id=None):
    level = 1
    if parent_id:
        conn = get_conn()
        parent = conn.execute("SELECT level FROM accounts WHERE id=?", (parent_id,)).fetchone()
        if parent:
            level = parent["level"] + 1
        conn.close()
    is_debit = "credit" if code.startswith(("2", "3", "4")) else "debit"
    conn = get_conn()
    conn.execute(
        "INSERT INTO accounts (code, name, parent_id, level, is_debit) VALUES (?,?,?,?,?)",
        (code, name, parent_id, level, is_debit)
    )
    conn.commit()
    conn.close()

def get_accounts_tree():
    conn = get_conn()
    accounts = conn.execute("SELECT * FROM accounts ORDER BY code").fetchall()
    conn.close()
    return accounts

def build_tree(accounts, parent_id=None, indent=0):
    tree = []
    for acc in accounts:
        if acc["parent_id"] == parent_id:
            tree.append(dict(acc, indent=indent))
            tree.extend(build_tree(accounts, acc["id"], indent + 1))
    return tree

def show():
    st.title("🧾 شجرة الحسابات")
    create_accounts_table()

    tab1, tab2 = st.tabs(["📊 عرض الشجرة", "➕ إضافة حساب"])

    with tab1:
        accounts = get_accounts_tree()
        if accounts:
            tree = build_tree(accounts)
            df = pd.DataFrame(tree)
            df["display_name"] = df.apply(lambda r: " " * r["indent"] + r["name"], axis=1)
            st.dataframe(df[["code", "display_name", "level", "is_debit"]].rename(
                columns={"display_name": "اسم الحساب", "code": "الكود", "level": "المستوى", "is_debit": "طبيعة الحساب"}
            ), use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد حسابات. أضف حسابات جديدة من التبويب الثاني.")

    with tab2:
        accounts = get_accounts_tree()
        account_options = {"لا شيء (حساب رئيسي)": None}
        for acc in accounts:
            prefix = " " * (acc["level"] - 1) if acc["level"] else ""
            account_options[f"{prefix}{acc['code']} - {acc['name']}"] = acc["id"]

        selected_parent = st.selectbox("الحساب الأب", list(account_options.keys()))
        parent_id = account_options[selected_parent]

        col1, col2 = st.columns(2)
        code = col1.text_input("كود الحساب")
        name = col2.text_input("اسم الحساب")

        if st.button("💾 حفظ الحساب"):
            if not code or not name:
                st.error("الكود والاسم مطلوبان")
            else:
                try:
                    add_account(code, name, parent_id)
                    st.success(f"تم إضافة الحساب {code} - {name}")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("الكود موجود مسبقاً")
