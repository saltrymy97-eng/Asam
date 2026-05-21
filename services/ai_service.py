# services/ai_service.py – منطق المساعد الذكي المطور (فهم عميق للأعمال)
import sqlite3
from datetime import datetime
from groq import Groq
import streamlit as st
import json

DB_PATH = "erp.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_ai_tables():
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            model TEXT,
            tab_name TEXT,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def query_groq(system_prompt, user_query, model="llama-3.3-70b-versatile", max_tokens=2000, temperature=0.3):
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content

def save_chat_history(session_id, role, content, model="", tab_name=""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO ai_chat_history (session_id, role, content, model, tab_name, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, role, content, model, tab_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def get_chat_history(session_id=None, limit=20):
    conn = get_conn()
    if session_id:
        rows = conn.execute("SELECT * FROM ai_chat_history WHERE session_id = ? ORDER BY id DESC LIMIT ?", (session_id, limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM ai_chat_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_chat_sessions():
    conn = get_conn()
    sessions = conn.execute("""
        SELECT session_id, MIN(timestamp) as first_message, COUNT(*) as message_count
        FROM ai_chat_history GROUP BY session_id ORDER BY first_message DESC LIMIT 10
    """).fetchall()
    conn.close()
    return [dict(s) for s in sessions]

def get_comprehensive_data():
    """جمع بيانات شاملة وعميقة عن النظام"""
    conn = get_conn()
    
    # المؤشرات المالية الأساسية
    revenue = conn.execute("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '4%'").fetchone()[0]
    expenses = conn.execute("SELECT COALESCE(SUM(debit)-SUM(credit),0) FROM journal_lines WHERE account_name LIKE '5%'").fetchone()[0]
    assets = conn.execute("SELECT COALESCE(SUM(debit)-SUM(credit),0) FROM journal_lines WHERE account_name LIKE '1%'").fetchone()[0]
    liabilities = conn.execute("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '2%'").fetchone()[0]
    equity = conn.execute("SELECT COALESCE(SUM(credit)-SUM(debit),0) FROM journal_lines WHERE account_name LIKE '3%'").fetchone()[0]
    
    # المخزون والمنتجات
    products = [dict(p) for p in conn.execute("SELECT name, quantity, reorder_level, selling_price, purchase_price FROM products").fetchall()]
    low_stock = [dict(p) for p in conn.execute("SELECT name, quantity FROM products WHERE quantity < reorder_level").fetchall()]
    
    # العملاء والموردين
    customers = [dict(c) for c in conn.execute("SELECT name, phone FROM customers").fetchall()]
    suppliers = [dict(s) for s in conn.execute("SELECT name, phone FROM suppliers").fetchall()]
    
    # الموظفين والرواتب
    employees = [dict(e) for e in conn.execute("""
        SELECT e.name, e.position, COALESCE(es.basic_salary,0) as basic_salary,
               COALESCE(es.housing_allowance,0) as housing, COALESCE(es.transport_allowance,0) as transport
        FROM employees e LEFT JOIN employee_salaries es ON e.id = es.employee_id
    """).fetchall()]
    
    # أحدث الفواتير
    recent_invoices = [dict(inv) for inv in conn.execute("""
        SELECT i.type, i.total, i.invoice_date, 
               CASE WHEN i.type='sale' THEN c.name ELSE s.name END as party
        FROM invoices i
        LEFT JOIN customers c ON i.party_id = c.id AND i.type='sale'
        LEFT JOIN suppliers s ON i.party_id = s.id AND i.type='purchase'
        ORDER BY i.id DESC LIMIT 10
    """).fetchall()]
    
    # المبيعات الشهرية
    monthly_sales = [dict(m) for m in conn.execute("""
        SELECT strftime('%Y-%m', invoice_date) as month, SUM(total) as total
        FROM invoices WHERE type='sale' AND status='completed'
        GROUP BY month ORDER BY month DESC LIMIT 12
    """).fetchall()]
    
    # النسب المالية
    profit_margin = (revenue - expenses) / revenue * 100 if revenue > 0 else 0
    debt_ratio = liabilities / assets * 100 if assets > 0 else 0
    roa = (revenue - expenses) / assets * 100 if assets > 0 else 0
    
    conn.close()
    
    return {
        "revenue": revenue, "expenses": expenses, "net_income": revenue - expenses,
        "assets": assets, "liabilities": liabilities, "equity": equity,
        "products": products, "low_stock": low_stock,
        "customers": customers, "suppliers": suppliers,
        "employees": employees, "recent_invoices": recent_invoices,
        "monthly_sales": monthly_sales,
        "profit_margin": profit_margin, "debt_ratio": debt_ratio, "roa": roa
    }

def get_inventory_data():
    conn = get_conn()
    low = [dict(r) for r in conn.execute("SELECT name, quantity, reorder_level FROM products WHERE quantity < reorder_level").fetchall()]
    allp = [dict(r) for r in conn.execute("SELECT name, quantity, reorder_level, selling_price FROM products").fetchall()]
    conn.close()
    return low, allp

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
    entries = [dict(r) for r in conn.execute("SELECT * FROM journal_entries ORDER BY id DESC LIMIT 50").fetchall()]
    conn.close()
    return entries

def get_all_accounts():
    conn = get_conn()
    accounts = [dict(r) for r in conn.execute("SELECT code, name FROM accounts ORDER BY code").fetchall()]
    conn.close()
    return accounts

def get_financial_ratios():
    data = get_comprehensive_data()
    return {
        "هامش الربح": f"{data['profit_margin']:.1f}%",
        "نسبة المديونية": f"{data['debt_ratio']:.1f}%",
        "العائد على الأصول": f"{data['roa']:.1f}%",
        "صافي الدخل": f"{data['net_income']:,.2f}"
    }

def get_trend_analysis():
    conn = get_conn()
    trends = conn.execute("""
        SELECT strftime('%Y-%m', invoice_date) as month,
               SUM(CASE WHEN type='sale' THEN total ELSE 0 END) as sales,
               SUM(CASE WHEN type='purchase' THEN total ELSE 0 END) as purchases
        FROM invoices WHERE status='completed'
        GROUP BY month ORDER BY month DESC LIMIT 6
    """).fetchall()
    conn.close()
    return [dict(t) for t in trends]

def get_top_customers(limit=5):
    conn = get_conn()
    customers = conn.execute("""
        SELECT c.name, COUNT(i.id) as invoice_count, SUM(i.total) as total
        FROM invoices i JOIN customers c ON i.party_id = c.id
        WHERE i.type='sale' AND i.status='completed'
        GROUP BY c.id ORDER BY total DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(c) for c in customers]

def get_top_suppliers(limit=5):
    conn = get_conn()
    suppliers = conn.execute("""
        SELECT s.name, COUNT(i.id) as invoice_count, SUM(i.total) as total
        FROM invoices i JOIN suppliers s ON i.party_id = s.id
        WHERE i.type='purchase' AND i.status='completed'
        GROUP BY s.id ORDER BY total DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(s) for s in suppliers]
