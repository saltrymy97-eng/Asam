# services/payroll_service.py – منطق كشوف الرواتب (PostgreSQL)
import psycopg2.extras
from datetime import date
from database import get_connection
from services.audit_service import log_action

def _dict_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def create_payroll_tables():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS employee_salaries (
            id SERIAL PRIMARY KEY,
            employee_id INTEGER UNIQUE REFERENCES employees(id),
            basic_salary REAL DEFAULT 0,
            housing_allowance REAL DEFAULT 0,
            transport_allowance REAL DEFAULT 0,
            other_allowances REAL DEFAULT 0,
            deductions REAL DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS payroll_runs (
            id SERIAL PRIMARY KEY,
            employee_id INTEGER REFERENCES employees(id),
            month TEXT NOT NULL,
            basic_salary REAL,
            housing_allowance REAL,
            transport_allowance REAL,
            other_allowances REAL,
            total_allowances REAL,
            deductions REAL,
            net_salary REAL,
            journal_entry_id INTEGER
        )
    """)
    conn.commit()
    conn.close()

def get_employees():
    conn = get_connection()
    c = _dict_cursor(conn)
    c.execute("SELECT id, name FROM employees")
    emps = c.fetchall()
    conn.close()
    return emps

def get_salary_config(employee_id):
    conn = get_connection()
    c = _dict_cursor(conn)
    c.execute("SELECT * FROM employee_salaries WHERE employee_id=%s", (employee_id,))
    conf = c.fetchone()
    conn.close()
    return conf

def save_salary_config(employee_id, basic, housing, transport, other, deductions):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM employee_salaries WHERE employee_id=%s", (employee_id,))
    exists = c.fetchone()
    if exists:
        c.execute("""
            UPDATE employee_salaries SET basic_salary=%s, housing_allowance=%s, transport_allowance=%s,
            other_allowances=%s, deductions=%s WHERE employee_id=%s
        """, (basic, housing, transport, other, deductions, employee_id))
    else:
        c.execute("""
            INSERT INTO employee_salaries (employee_id, basic_salary, housing_allowance, transport_allowance, other_allowances, deductions)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (employee_id, basic, housing, transport, other, deductions))
    conn.commit()
    conn.close()

def calculate_net(basic, housing, transport, other, deductions):
    total_allowances = housing + transport + other
    net = basic + total_allowances - deductions
    return total_allowances, net

def run_payroll(employee_id, month):
    """تشغيل كشف الراتب لشهر محدد وإنشاء قيد محاسبي مع إدارة العمليات"""
    conf = get_salary_config(employee_id)
    if not conf:
        return None, "لا توجد إعدادات راتب للموظف"

    basic = conf["basic_salary"]
    housing = conf["housing_allowance"]
    transport = conf["transport_allowance"]
    other = conf["other_allowances"]
    deductions = conf["deductions"]
    total_allowances, net = calculate_net(basic, housing, transport, other, deductions)

    conn = get_connection()

    try:
        conn.execute("BEGIN")
        c = conn.cursor()

        desc = f"راتب شهر {month}"
        c.execute(
            "INSERT INTO journal_entries (date, description, reference) VALUES (%s, %s, %s) RETURNING id",
            (date.today().strftime("%Y-%m-%d"), desc, month)
        )
        entry_id = c.fetchone()[0]

        c.execute(
            "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (%s, 'مصروف الرواتب', %s, 0)",
            (entry_id, basic + total_allowances)
        )
        c.execute(
            "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (%s, 'البنك', 0, %s)",
            (entry_id, net)
        )
        if deductions > 0:
            c.execute(
                "INSERT INTO journal_lines (entry_id, account_name, debit, credit) VALUES (%s, 'خصومات الموظفين', 0, %s)",
                (entry_id, deductions)
            )

        c.execute("""
            INSERT INTO payroll_runs (employee_id, month, basic_salary, housing_allowance, transport_allowance,
            other_allowances, total_allowances, deductions, net_salary, journal_entry_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (employee_id, month, basic, housing, transport, other, total_allowances, deductions, net, entry_id))

        conn.commit()
        return net, None

    except Exception as e:
        conn.rollback()
        return None, str(e)
    finally:
        conn.close()

def get_payroll_history(month=None):
    conn = get_connection()
    c = _dict_cursor(conn)
    query = """
        SELECT pr.id, e.name, pr.month, pr.basic_salary, pr.total_allowances,
               pr.deductions, pr.net_salary, pr.journal_entry_id
        FROM payroll_runs pr
        JOIN employees e ON pr.employee_id = e.id
    """
    params = ()
    if month:
        query += " WHERE pr.month = %s"
        params = (month,)
    query += " ORDER BY pr.month DESC, e.name"
    c.execute(query, params)
    records = c.fetchall()
    conn.close()
    return records
