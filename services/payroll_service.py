# services/payroll_service.py – منطق كشوف الرواتب (v2.0)
# ✅ Registry + فحص الرصيد + دعم البنك والصندوق + تسجيل الحركة
import sqlite3
from datetime import date
from database import get_connection, close_connection
from services.audit_service import log_action
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry


def create_payroll_tables(conn=None):
    """إنشاء جداول الرواتب وإعدادات الموظفين إذا لم تكن موجودة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
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
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            close_connection(conn)


def get_employees(conn=None):
    """جلب قائمة الموظفين"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        emps = conn.execute("SELECT id, name FROM employees").fetchall()
        return [dict(e) for e in emps]
    finally:
        if own_conn:
            close_connection(conn)


def get_salary_config(employee_id, conn=None):
    """جلب إعدادات الراتب لموظف محدد"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conf = conn.execute(
            "SELECT * FROM employee_salaries WHERE employee_id=?",
            (employee_id,)
        ).fetchone()
        return dict(conf) if conf else None
    finally:
        if own_conn:
            close_connection(conn)


def save_salary_config(employee_id, basic, housing, transport, other,
                       deductions, conn=None):
    """حفظ أو تحديث إعدادات الراتب للموظف"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        if own_conn:
            conn.execute("BEGIN")
        exists = conn.execute(
            "SELECT id FROM employee_salaries WHERE employee_id=?",
            (employee_id,)
        ).fetchone()
        if exists:
            conn.execute("""
                UPDATE employee_salaries SET basic_salary=?,
                housing_allowance=?, transport_allowance=?,
                other_allowances=?, deductions=? WHERE employee_id=?
            """, (basic, housing, transport, other, deductions, employee_id))
        else:
            conn.execute("""
                INSERT INTO employee_salaries 
                (employee_id, basic_salary, housing_allowance, transport_allowance,
                 other_allowances, deductions)
                VALUES (?,?,?,?,?,?)
            """, (employee_id, basic, housing, transport, other, deductions))
        if own_conn:
            conn.commit()
        return True, None
    except Exception as e:
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return False, str(e)
    finally:
        if own_conn:
            close_connection(conn)


def calculate_net(basic, housing, transport, other, deductions):
    """حساب إجمالي البدلات وصافي الراتب"""
    total_allowances = housing + transport + other
    net = basic + total_allowances - deductions
    return total_allowances, net


def run_payroll(employee_id, month, payment_account_code=None,
                payment_method="bank", conn=None):
    """
    تشغيل كشف الراتب لشهر محدد.
    
    Args:
        employee_id:           معرف الموظف
        month:                 الشهر (YYYY-MM)
        payment_account_code:  كود الصندوق/البنك (يُختار في الواجهة)
        payment_method:        'cash' | 'bank'
    
    Returns:
        (net, None)         عند النجاح
        (None, "رسالة")     عند الفشل
    """
    conf = get_salary_config(employee_id, conn=conn)
    if not conf:
        return None, "لا توجد إعدادات راتب للموظف"

    basic = float(conf["basic_salary"] or 0)
    housing = float(conf["housing_allowance"] or 0)
    transport = float(conf["transport_allowance"] or 0)
    other = float(conf["other_allowances"] or 0)
    deductions = float(conf["deductions"] or 0)

    total_allowances, net = calculate_net(basic, housing, transport, other, deductions)
    gross_salary = basic + total_allowances

    if net <= 0:
        return None, "صافي الراتب يجب أن يكون أكبر من صفر"

    # ✅ فحص الرصيد قبل الصرف
    if payment_account_code and payment_method in ('cash', 'bank'):
        from services.cash_service import check_sufficient_balance
        ok, err = check_sufficient_balance(payment_account_code, net, conn=conn)
        if not ok:
            return None, f"لا يمكن صرف الراتب: {err}"
    else:
        return None, "يجب تحديد حساب الدفع (صندوق أو بنك)"

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        # جلب اسم الموظف
        emp = conn.execute(
            "SELECT name FROM employees WHERE id=?", (employee_id,)
        ).fetchone()
        emp_name = emp["name"] if emp else "موظف غير معروف"

        if own_conn:
            conn.execute("BEGIN")

        # 1. الحسابات الوظيفية
        acc_salaries_exp = get_functional_account("salaries_expense")
        acc_accrued = get_functional_account("accrued_expenses")
        acc_payment = payment_account_code  # الصندوق أو البنك

        if not acc_salaries_exp:
            raise Exception("لم يتم العثور على حساب مصروف الرواتب (salaries_expense)")
        if not acc_accrued:
            acc_accrued = get_functional_account("accounts_payable")

        # 2. بناء القيد:
        #    مدين: مصروف الرواتب (الإجمالي)
        #    دائن: حساب الدفع (الصافي) + مستحقات (الاستقطاعات)
        lines = [
            {
                "account": acc_salaries_exp,
                "debit": gross_salary,
                "credit": 0,
                "currency_code": "YER",
                "exchange_rate": 1.0,
            },
            {
                "account": acc_payment,
                "debit": 0,
                "credit": net,
                "currency_code": "YER",
                "exchange_rate": 1.0,
            },
        ]

        if deductions > 0:
            lines.append({
                "account": acc_accrued,
                "debit": 0,
                "credit": deductions,
                "currency_code": "YER",
                "exchange_rate": 1.0,
            })

        # 3. حفظ القيد
        entry_id, entry_error = save_journal_entry(
            description=f"راتب شهر {month} - الموظف: {emp_name}",
            lines=lines,
            entry_date=date.today().strftime("%Y-%m-%d"),
            conn=conn,
        )
        if entry_error:
            raise Exception(f"فشل إنشاء القيد المحاسبي: {entry_error}")

        # 4. تسجيل مسير الراتب
        conn.execute("""
            INSERT INTO payroll_runs 
                (employee_id, month, basic_salary, housing_allowance,
                 transport_allowance, other_allowances, total_allowances,
                 deductions, net_salary, journal_entry_id)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (employee_id, month, basic, housing, transport, other,
              total_allowances, deductions, net, entry_id))

        # 5. ✅ تسجيل حركة الصندوق/البنك
        if payment_method == 'cash':
            try:
                from services.cash_service import add_cash_transaction
                acc_row = conn.execute(
                    "SELECT id FROM cash_accounts WHERE account_code=? AND is_active=1 LIMIT 1",
                    (payment_account_code,)
                ).fetchone()
                if acc_row:
                    add_cash_transaction(
                        acc_row['id'],
                        date.today().strftime("%Y-%m-%d"),
                        f"راتب {month} - {emp_name}",
                        'withdrawal',
                        net,
                        reference=f"payroll#{employee_id}_{month}",
                        create_journal=False,
                        conn=conn,
                        skip_balance_check=True,
                    )
            except Exception as e:
                print(f"⚠️ فشل تسجيل حركة الصندوق: {e}")

        elif payment_method == 'bank':
            try:
                from services.bank_service import add_bank_transaction
                acc_row = conn.execute(
                    "SELECT id FROM bank_accounts WHERE account_code=? AND is_active=1 LIMIT 1",
                    (payment_account_code,)
                ).fetchone()
                if acc_row:
                    add_bank_transaction(
                        acc_row['id'],
                        date.today().strftime("%Y-%m-%d"),
                        f"راتب {month} - {emp_name}",
                        'withdrawal',
                        net,
                        reference=f"payroll#{employee_id}_{month}",
                        conn=conn,
                        skip_balance_check=True,
                    )
            except Exception as e:
                print(f"⚠️ فشل تسجيل حركة البنك: {e}")

        if own_conn:
            conn.commit()

        log_action(
            username="admin",
            action="تشغيل راتب",
            table_name="payroll_runs",
            record_id=entry_id,
            new_value=f"الموظف: {emp_name}, الشهر: {month}, الصافي: {net:,.2f}"
        )

        return net, None

    except Exception as e:
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return None, str(e)
    finally:
        if own_conn:
            close_connection(conn)


def get_payroll_history(month=None, conn=None):
    """جلب سجل مسيرات الرواتب"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        query = """
            SELECT pr.id, e.name, pr.month, pr.basic_salary,
                   pr.total_allowances, pr.deductions, pr.net_salary,
                   pr.journal_entry_id
            FROM payroll_runs pr
            JOIN employees e ON pr.employee_id = e.id
        """
        params = ()
        if month:
            query += " WHERE pr.month = ?"
            params = (month,)
        query += " ORDER BY pr.month DESC, e.name"
        records = conn.execute(query, params).fetchall()
        return [dict(r) for r in records]
    finally:
        if own_conn:
            close_connection(conn)
