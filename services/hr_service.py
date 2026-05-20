# services/hr_service.py – منطق الموارد البشرية (مع إدارة العمليات)
import sqlite3
from database import get_connection
from services.audit_service import log_action

def get_all_employees():
    """جلب جميع الموظفين"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    employees = conn.execute("SELECT * FROM employees ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(e) for e in employees]

def add_employee(name, position, salary, join_date, username="admin"):
    """إضافة موظف جديد مع حماية العملية"""
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO employees (name, position, salary, join_date) VALUES (?, ?, ?, ?)",
            (name, position, salary, join_date)
        )
        conn.commit()
        
        log_action(
            username=username,
            action="إضافة موظف",
            table_name="employees",
            new_value=f"الموظف: {name}, المنصب: {position}"
        )
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_employees_for_select():
    """جلب الموظفين للاختيار (id, name)"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    employees = conn.execute("SELECT id, name FROM employees ORDER BY name").fetchall()
    conn.close()
    return [dict(e) for e in employees]

def record_attendance(employee_id, employee_name, date_str, status, username="admin"):
    """تسجيل حضور مع حماية العملية"""
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO attendance (employee_id, date, status) VALUES (?, ?, ?)",
            (employee_id, date_str, status)
        )
        conn.commit()
        
        log_action(
            username=username,
            action="تسجيل حضور",
            table_name="attendance",
            new_value=f"الموظف: {employee_name}, التاريخ: {date_str}, الحالة: {status}"
        )
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_attendance_history():
    """سجل الحضور"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    attendance = conn.execute("""
        SELECT a.date, e.name, a.status 
        FROM attendance a
        JOIN employees e ON a.employee_id = e.id
        ORDER BY a.date DESC, e.name
    """).fetchall()
    conn.close()
    return [dict(a) for a in attendance]
