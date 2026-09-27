# services/vat_service.py – وحدة إدارة ضريبة القيمة المضافة (v2.0)
# ✅ Registry + conn=None + إصلاح account_name + دفع الضريبة
import sqlite3
from datetime import date
from database import get_connection, close_connection
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry
from services.audit_service import log_action


def create_vat_table(conn=None):
    """إنشاء وتحديث جدول إعدادات الضريبة بأمان"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vat_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT DEFAULT 'ضريبة القيمة المضافة',
                rate REAL NOT NULL DEFAULT 0.15,
                is_active INTEGER DEFAULT 1 CHECK(is_active IN (0,1)),
                created_at TEXT
            )
        """)

        columns = [row[1] for row in conn.execute(
            "PRAGMA table_info(vat_config)"
        ).fetchall()]

        if 'name' not in columns:
            try:
                conn.execute(
                    "ALTER TABLE vat_config ADD COLUMN name TEXT "
                    "DEFAULT 'ضريبة القيمة المضافة'"
                )
            except sqlite3.OperationalError:
                pass

        if 'created_at' not in columns:
            try:
                conn.execute("ALTER TABLE vat_config ADD COLUMN created_at TEXT")
            except sqlite3.OperationalError:
                pass

        count = conn.execute("SELECT COUNT(*) FROM vat_config").fetchone()[0]
        if count == 0:
            conn.execute(
                "INSERT INTO vat_config (name, rate, is_active) "
                "VALUES ('ضريبة القيمة المضافة', 0.15, 1)"
            )

        if own_conn:
            conn.commit()
    except Exception:
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
    finally:
        if own_conn:
            close_connection(conn)


# ========== إعدادات ونسب الضريبة ==========

def get_vat_rate(conn=None):
    """جلب نسبة الضريبة الحالية المفعلة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        row = conn.execute(
            "SELECT rate FROM vat_config WHERE is_active = 1 "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return row["rate"] if row else 0.15
    except Exception:
        return 0.15
    finally:
        if own_conn:
            close_connection(conn)


def update_vat_rate(new_rate, name="ضريبة القيمة المضافة", conn=None):
    """تحديث نسبة الضريبة وأرشفة النسب القديمة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        if own_conn:
            conn.execute("BEGIN")
        conn.execute("UPDATE vat_config SET is_active = 0")
        conn.execute(
            "INSERT INTO vat_config (name, rate, is_active) VALUES (?, ?, 1)",
            (name, new_rate)
        )
        if own_conn:
            conn.commit()

        log_action(
            username="admin",
            action="تحديث نسبة الضريبة",
            table_name="vat_config",
            new_value=f"النسبة الجديدة: {new_rate * 100}%"
        )
        return True, "تم تحديث نسبة الضريبة بنجاح"
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


def get_vat_history(conn=None):
    """جلب سجل تغييرات نسب الضريبة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        rows = conn.execute(
            "SELECT * FROM vat_config ORDER BY id DESC LIMIT 20"
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        if own_conn:
            close_connection(conn)


# ========== الحسابات ==========

def calculate_vat(amount, rate=None):
    """حساب قيمة الضريبة لمبلغ صافي"""
    if rate is None:
        rate = get_vat_rate()
    return round(amount * rate, 2)


def calculate_reverse_vat(total_amount, rate=None):
    """احتساب المبلغ قبل الضريبة وقيمة الضريبة من المبلغ الإجمالي"""
    if rate is None:
        rate = get_vat_rate()
    before_vat = round(total_amount / (1 + rate), 2)
    vat_amount = round(total_amount - before_vat, 2)
    return before_vat, vat_amount


# ========== تقارير الضريبة ==========

def get_vat_report(start_date=None, end_date=None, conn=None):
    """تقرير ملخص الضريبة لفترة محددة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        date_clause = ""
        params = []
        if start_date and end_date:
            date_clause = " AND invoice_date BETWEEN ? AND ?"
            params = [start_date, end_date]

        sales = conn.execute(
            f"SELECT COALESCE(SUM(total), 0), COALESCE(SUM(vat_amount), 0) "
            f"FROM invoices WHERE type='sale' AND status='completed'{date_clause}",
            params
        ).fetchone()

        purchases = conn.execute(
            f"SELECT COALESCE(SUM(total), 0), COALESCE(SUM(vat_amount), 0) "
            f"FROM invoices WHERE type='purchase' AND status='completed'{date_clause}",
            params
        ).fetchone()

        total_sales = sales[0]
        output_vat = sales[1]
        total_purchases = purchases[0]
        input_vat = purchases[1]
        net_vat = round(output_vat - input_vat, 2)

        return {
            "rate": get_vat_rate(conn=conn),
            "total_sales": total_sales,
            "total_purchases": total_purchases,
            "output_vat": output_vat,
            "input_vat": input_vat,
            "net_vat": net_vat,
        }
    finally:
        if own_conn:
            close_connection(conn)


def get_tax_return_report(start_date=None, end_date=None, conn=None):
    """تقرير الإقرار الضريبي التفصيلي"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        date_clause = ""
        params = []
        if start_date and end_date:
            date_clause = " AND invoice_date BETWEEN ? AND ?"
            params = [start_date, end_date]

        sales_data = conn.execute(
            f"SELECT COALESCE(SUM(vat_amount),0), "
            f"COALESCE(SUM(total - vat_amount),0) "
            f"FROM invoices WHERE type='sale' AND status='completed'{date_clause}",
            params
        ).fetchone()

        purchases_data = conn.execute(
            f"SELECT COALESCE(SUM(vat_amount),0), "
            f"COALESCE(SUM(total - vat_amount),0) "
            f"FROM invoices WHERE type='purchase' AND status='completed'{date_clause}",
            params
        ).fetchone()

        invoices = conn.execute(
            f"SELECT id, type, invoice_date, total, vat_amount, vat_rate, "
            f"COALESCE(reference, CAST(id AS TEXT)) AS invoice_number "
            f"FROM invoices WHERE status='completed'{date_clause} "
            f"ORDER BY invoice_date DESC",
            params
        ).fetchall()

        output_vat = sales_data[0]
        input_vat = purchases_data[0]
        net_vat = round(output_vat - input_vat, 2)

        return {
            "rate": get_vat_rate(conn=conn),
            "total_output_vat": output_vat,
            "total_input_vat": input_vat,
            "net_vat": net_vat,
            "sales_before_tax": sales_data[1],
            "purchases_before_tax": purchases_data[1],
            "invoices": [dict(inv) for inv in invoices],
        }
    finally:
        if own_conn:
            close_connection(conn)


# ============================================================
# ✅ إصلاح: post_vat_settlement_entry — استخدم "account" بدل "account_name"
# ============================================================
def post_vat_settlement_entry(settlement_date, start_date, end_date,
                               description="تسوية وإقفال ضريبة القيمة المضافة للفترة",
                               conn=None):
    """توليد قيد تسوية آلي لإقفال حسابات الضريبة"""
    report = get_vat_report(start_date, end_date, conn=conn)
    output_vat = report['output_vat']
    input_vat = report['input_vat']
    net_vat = report['net_vat']

    if output_vat == 0 and input_vat == 0:
        return False, "لا توجد مبالغ ضريبية مستحقة للتسوية خلال هذه الفترة"

    vat_output_acc = get_functional_account("sales_tax")
    vat_input_acc = get_functional_account("purchase_tax")
    vat_payable_acc = get_functional_account("sales_tax")

    lines = [
        # إقفال ضريبة المخرجات
        {
            "account": vat_output_acc,          # ✅ صحيح
            "debit": output_vat,
            "credit": 0.0,
            "currency_code": "YER",
            "exchange_rate": 1.0,
        },
        # إقفال ضريبة المدخلات
        {
            "account": vat_input_acc,           # ✅ صحيح
            "debit": 0.0,
            "credit": input_vat,
            "currency_code": "YER",
            "exchange_rate": 1.0,
        },
    ]

    if net_vat > 0:
        lines.append({
            "account": vat_payable_acc,
            "debit": 0.0,
            "credit": net_vat,
            "currency_code": "YER",
            "exchange_rate": 1.0,
        })
    elif net_vat < 0:
        lines.append({
            "account": vat_payable_acc,
            "debit": abs(net_vat),
            "credit": 0.0,
            "currency_code": "YER",
            "exchange_rate": 1.0,
        })

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        journal_id, err = save_journal_entry(
            entry_date=settlement_date,
            description=f"{description} ({start_date} إلى {end_date})",
            lines=lines,
            conn=conn,
        )
        if err:
            return False, f"فشل القيد: {err}"

        if own_conn:
            conn.commit()

        log_action(
            username="admin",
            action="إصدار قيد تسوية الضريبة",
            table_name="journal_entries",
            record_id=journal_id,
            new_value=f"رقم القيد: {journal_id}, الصافي: {net_vat}"
        )
        return True, f"تم إنشاء قيد التسوية الضريبية بنجاح برقم قيد: {journal_id}"
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


# ============================================================
# ✅ جديد: دفع الضريبة من بنك/صندوق
# ============================================================
def pay_vat(amount, payment_date, payment_account_code, payment_method="bank",
            reference="", notes="", created_by="admin", conn=None):
    """
    تسجيل دفع الضريبة لجهة الضرائب.
    
    Args:
        amount:               المبلغ المدفوع
        payment_date:         تاريخ الدفع (YYYY-MM-DD)
        payment_account_code: كود الصندوق أو البنك
        payment_method:       'cash' | 'bank'
    
    Returns:
        (journal_id, None)      عند النجاح
        (None, "رسالة")         عند الفشل
    """
    amount = float(amount)
    if amount <= 0:
        return None, "المبلغ يجب أن يكون أكبر من صفر"

    if payment_method not in ('cash', 'bank'):
        return None, "طريقة الدفع يجب أن تكون cash أو bank"

    # ✅ فحص الرصيد
    from services.cash_service import check_sufficient_balance
    ok, err = check_sufficient_balance(payment_account_code, amount, conn=conn)
    if not ok:
        return None, f"لا يمكن دفع الضريبة: {err}"

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN")

        vat_payable_acc = get_functional_account("sales_tax")

        if not vat_payable_acc:
            raise Exception("حساب ضريبة المخرجات (sales_tax) غير معرف")

        # القيد: مدين الضريبة / دائن صندوق أو بنك
        lines = [
            {
                "account": vat_payable_acc,
                "debit": amount,
                "credit": 0.0,
                "currency_code": "YER",
                "exchange_rate": 1.0,
            },
            {
                "account": payment_account_code,
                "debit": 0.0,
                "credit": amount,
                "currency_code": "YER",
                "exchange_rate": 1.0,
            },
        ]

        journal_id, err = save_journal_entry(
            entry_date=payment_date,
            description=f"دفع ضريبة القيمة المضافة - {reference}",
            lines=lines,
            conn=conn,
        )
        if err:
            raise Exception(f"فشل القيد: {err}")

        # ✅ تسجيل الحركة في الصندوق/البنك
        if payment_method == 'cash':
            try:
                from services.cash_service import add_cash_transaction
                acc_row = conn.execute(
                    "SELECT id FROM cash_accounts WHERE account_code=? AND is_active=1 LIMIT 1",
                    (payment_account_code,)
                ).fetchone()
                if acc_row:
                    add_cash_transaction(
                        acc_row['id'], payment_date,
                        f"دفع ضريبة - {reference}",
                        'withdrawal', amount,
                        reference=f"vat_payment#{journal_id}",
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
                        acc_row['id'], payment_date,
                        f"دفع ضريبة - {reference}",
                        'withdrawal', amount,
                        reference=f"vat_payment#{journal_id}",
                        conn=conn,
                        skip_balance_check=True,
                    )
            except Exception as e:
                print(f"⚠️ فشل تسجيل حركة البنك: {e}")

        if own_conn:
            conn.commit()

        log_action(
            username=created_by,
            action="دفع ضريبة القيمة المضافة",
            table_name="journal_entries",
            record_id=journal_id,
            new_value=f"المبلغ: {amount:,.2f} من {payment_account_code}"
        )

        return journal_id, None

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
