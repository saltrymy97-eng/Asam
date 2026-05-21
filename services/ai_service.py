# services/ai_service.py – منطق المساعد الذكي
import sqlite3
from groq import Groq
import streamlit as st

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

def query_groq(system_prompt, user_query, max_tokens=1500):
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        temperature=0.3,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content

def get_comprehensive_data():
    conn = get_conn()
    revenue = conn.execute("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '4%'").fetchone()[0]
    expenses = conn.execute("SELECT COALESCE(SUM(debit)-SUM(credit),0) FROM journal_lines WHERE account_name LIKE '5%'").fetchone()[0]
    assets = conn.execute("SELECT COALESCE(SUM(debit)-SUM(credit),0) FROM journal_lines WHERE account_name LIKE '1%'").fetchone()[0]
    liabilities = conn.execute("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '2%'").fetchone()[0]
    equity = conn.execute("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '3%'").fetchone()[0]
    
    products = [dict(p) for p in conn.execute("SELECT name, quantity, reorder_level, selling_price, purchase_price FROM products").fetchall()]
    customers = [dict(c) for c in conn.execute("SELECT name, phone FROM customers").fetchall()]
    suppliers = [dict(s) for s in conn.execute("SELECT name, phone FROM suppliers").fetchall()]
    employees = [dict(emp) for emp in conn.execute("""
        SELECT e.name, e.position, es.basic_salary, es.housing_allowance, es.transport_allowance, es.deductions
        FROM employees e LEFT JOIN employee_salaries es ON e.id = es.employee_id
    """).fetchall()]
    invoices = [dict(inv) for inv in conn.execute("SELECT type, invoice_date, total, status FROM invoices ORDER BY id DESC LIMIT 10").fetchall()]
    stock = [dict(s) for s in conn.execute("""
        SELECT sm.type, sm.quantity, sm.date, p.name
        FROM stock_movements sm JOIN products p ON sm.product_id = p.id ORDER BY sm.id DESC LIMIT 10
    """).fetchall()]
    entries = [dict(e) for e in conn.execute("SELECT date, description FROM journal_entries ORDER BY id DESC LIMIT 5").fetchall()]
    monthly_sales = [dict(m) for m in conn.execute("""
        SELECT strftime('%Y-%m', invoice_date) as month, SUM(total) as total
        FROM invoices WHERE type='sale' AND status='completed' GROUP BY month ORDER BY month DESC LIMIT 12
    """).fetchall()]
    monthly_purchases = [dict(m) for m in conn.execute("""
        SELECT strftime('%Y-%m', invoice_date) as month, SUM(total) as total
        FROM invoices WHERE type='purchase' AND status='completed' GROUP BY month ORDER BY month DESC LIMIT 12
    """).fetchall()]
    stock_consumption = [dict(s) for s in conn.execute("""
        SELECT p.name, COALESCE(SUM(CASE WHEN sm.type='out' THEN sm.quantity ELSE 0 END), 0) as total_out,
               COUNT(DISTINCT strftime('%Y-%m', sm.date)) as months_count
        FROM products p LEFT JOIN stock_movements sm ON p.id = sm.product_id GROUP BY p.id
    """).fetchall()]
    conn.close()
    
    return {
        "revenue": revenue, "expenses": expenses, "net_income": revenue - expenses,
        "assets": assets, "liabilities": liabilities, "equity": equity,
        "products": products, "customers": customers, "suppliers": suppliers,
        "employees": employees, "recent_invoices": invoices, "recent_stock": stock,
        "recent_entries": entries, "monthly_sales": monthly_sales,
        "monthly_purchases": monthly_purchases, "stock_consumption": stock_consumption
    }

def get_inventory_data():
    conn = get_conn()
    low_stock = [dict(r) for r in conn.execute("SELECT name, quantity, reorder_level FROM products WHERE quantity < reorder_level").fetchall()]
    all_products = [dict(r) for r in conn.execute("SELECT name, quantity, reorder_level FROM products").fetchall()]
    conn.close()
    return low_stock, all_products

def get_employee_info(name):
    conn = get_conn()
    emp = conn.execute("SELECT * FROM employees WHERE name LIKE ?", (f"%{name}%",)).fetchone()
    if emp:
        sal = conn.execute("SELECT * FROM employee_salaries WHERE employee_id=?", (emp["id"],)).fetchone()
        conn.close()
        return dict(emp), dict(sal) if sal else None
    conn.close()
    return None, None

def get_recent_entries():
    conn = get_conn()
    entries = [dict(r) for r in conn.execute("SELECT * FROM journal_entries ORDER BY id DESC LIMIT 20").fetchall()]
    conn.close()
    return entries

def get_all_accounts():
    conn = get_conn()
    accounts = [dict(r) for r in conn.execute("SELECT code, name FROM accounts ORDER BY code").fetchall()]
    conn.close()
    return accounts
