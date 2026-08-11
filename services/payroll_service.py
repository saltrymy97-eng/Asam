# services/payroll_service.py – منطق كشوف الرواتب (SQLite - دعم الحسابات الوظيفية)
import sqlite3
from datetime import date
from database import get_connection
from services.audit_service import log_action
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry

def create_payroll_tables():
    """إنشاء جداول الرواتب وإعدادات الموظفين إذا لم تكن موجودة"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS employee_salaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER UNIQUE,
            basic_salary REAL DEFAULT 0,
            housing_allowance REAL DEFAULT 0,
            transport_allowance REAL DEFAULT 0,
            other_allowances REAL DEFAULT 0,
            deductions REAL DEFAULT 0,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payroll_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            month TEXT NOT NULL,
            basic_salary REAL,
            housing_allowance REAL,
            transport_allowance REAL,
            other_allowances REAL,
            total_allowances REAL,
            deductions REAL,
            net_salary REAL,
            journal_entry_id INTEGER,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)
    conn.commit()
    conn.close()

def get_employees():
    """جلب قائمة الموظفين"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    emps = conn.execute("SELECT id, name FROM employees").fetchall()
    conn.close()
    return emps

def get_salary_config(employee_id):
    """جلب إعدادات الراتب لموظف محدد"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    conf = conn.execute("SELECT * FROM employee_salaries WHERE employee_id=?", (employee_id,)).fetchone()
    conn.close()
    return conf

def save_salary_config(employee_id, basic, housing, transport, other, deductions):
    """حفظ أو تحديث إعدادات الراتب للموظف"""
    conn = get_connection()
    exists = conn.execute("SELECT id FROM employee_salaries WHERE employee_id=?", (employee_id,)).fetchone()
    if exists:
        conn.execute("""
            UPDATE employee_salaries SET basic_salary=?, housing_allowance=?, transport_allowance=?,
            other_allowances=?, deductions=? WHERE employee_id=?
        """, (basic, housing, transport, other, deductions, employee_id))
    else:
        conn.execute("""
            INSERT INTO employee_salaries (employee_id, basic_salary, housing_allowance, transport_allowance, other_allowances, deductions)
            VALUES (?,?,?,?,?,?)
        """, (employee_id, basic, housing, transport, other, deductions))
    conn.commit()
    conn.close()

def calculate_net(basic, housing, transport, other, deductions):
    """حساب إجمالي البدلات وصافي الراتب"""
    total_allowances = housing + transport + other
    net = basic + total_allowances - deductions
    return total_allowances, net

def run_payroll(employee_id, month):
    """تشغيل كشف الراتب لشهر محدد وإنشاء قيد محاسبي عبر الحسابات الوظيفية"""
    conf = get_salary_config(employee_id)
    if not conf:
        return None, "لا توجد إعدادات راتب للموظف"

    basic = conf["basic_salary"]
    housing = conf["housing_allowance"]
    transport = conf["transport_allowance"]
    other = conf["other_allowances"]
    deductions = conf["deductions"]
    total_allowances, net = calculate_net(basic, housing, transport, other, deductions)
    gross_salary = basic + total_allowances

    conn = get_connection()
    conn.row_factory = sqlite3.Row

    try:
        # جلب اسم الموظف
        emp = conn.execute("SELECT name FROM employees WHERE id=?", (employee_id,)).fetchone()
        emp_name = emp["name"] if emp else "موظف غير معروف"

        conn.execute("BEGIN")

        # 1. جلب الحسابات الوظيفية
        acc_salaries_exp = get_functional_account("salaries_expense")
        acc_bank = get_functional_account("bank")
        acc_accrued = get_functional_account("accrued_expenses")

        # 2. تجهيز بنود القيد المحاسبي
        lines = [
            # مدين: إجمالي الرواتب والبدلات (مصروف الرواتب)
            {
                "account": acc_salaries_exp,
                "debit": gross_salary,
                "credit": 0,
                "currency_code": "YER",
                "exchange_rate": 1.0
            },
            # دائن: صافي الراتب المدفوع من البنك/النقدية
            {
                "account": acc_bank,
                "debit": 0,
                "credit": net,
                "currency_code": "YER",
                "exchange_rate": 1.0
            }
        ]

        # إذا كانت هناك استقطاعات، تضاف كمركب دائن في حساب المصروفات/الالتزامات المستحقة
        if deductions > 0:
            lines.append({
                "account": acc_accrued,
                "debit": 0,
                "credit": deductions,
                "currency_code": "YER",
                "exchange_rate": 1.0
            })

        # 3. حفظ القيد المحاسبي
        entry_desc = f"راتب شهر {month} - الموظف: {emp_name}"
        entry_id, entry_error = save_journal_entry(
            description=entry_desc,
            lines=lines,
            entry_date=date.today().strftime("%Y-%m-%d"),
            conn=conn
        )

        if entry_error:
            raise Exception(f"فشل إنشاء القيد المحاسبي للراتب: {entry_error}")

        # 4. تسجيل مسير الراتب في الجدول
        conn.execute("""
            INSERT INTO payroll_runs (employee_id, month, basic_salary, housing_allowance, transport_allowance,
            other_allowances, total_allowances, deductions, net_salary, journal_entry_id)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (employee_id, month, basic, housing, transport, other, total_allowances, deductions, net, entry_id))

        conn.commit()

        # 5. تسجيل العملية في سجل التدقيق
        log_action(
            username="admin",
            action="تشغيل راتب",
            table_name="payroll_runs",
            record_id=entry_id,
            new_value=f"الموظف: {emp_name}, الشهر: {month}, الصافي: {net:,.2f}"
        )

        return net, None

    except Exception as e:
        conn.rollback()
        return None, str(e)
    finally:
        conn.close()

def get_payroll_history(month=None):
    """جلب سجل مسيرات الرواتب"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    query = """
        SELECT pr.id, e.name, pr.month, pr.basic_salary, pr.total_allowances, pr.deductions, pr.net_salary, pr.journal_entry_id
        FROM payroll_runs pr
        JOIN employees e ON pr.employee_id = e.id
    """
    params = ()
    if month:
        query += " WHERE pr.month = ?"
        params = (month,)
    query += " ORDER BY pr.month DESC, e.name"
    records = conn.execute(query, params).fetchall()
    conn.close()
    return records
