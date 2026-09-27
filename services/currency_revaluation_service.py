# services/currency_revaluation_service.py – إعادة تقييم العملات (v2.0)
# ✅ conn=None + BEGIN IMMEDIATE + تحديث أرصدة الصندوق/البنك
import sqlite3
from datetime import date
from database import get_connection, close_connection
from services.audit_service import log_action
from services.currency_service import get_base_currency, get_exchange_rate
from services.accounting_service import save_journal_entry
from services.chart_service import get_functional_account


# ============================================================
# مساعدات
# ============================================================
def _resolve_conn(conn):
    if conn is None:
        return get_connection(), True
    return conn, False


def _release_conn(conn, owns):
    if owns:
        close_connection(conn)


def _validate_rate(rate) -> tuple[bool, float, str]:
    try:
        r = float(rate)
        if r <= 0:
            return False, 0, "سعر الصرف يجب أن يكون أكبر من صفر"
        return True, r, ""
    except (TypeError, ValueError):
        return False, 0, f"سعر صرف غير صالح: {rate}"


def _validate_date(d) -> tuple[bool, str]:
    if not d:
        return True, date.today().strftime("%Y-%m-%d")
    try:
        date.fromisoformat(str(d)[:10])
        return True, str(d)[:10]
    except ValueError:
        return False, f"تاريخ غير صالح: {d}"


# ============================================================
# جلب الحسابات ذات العملات الأجنبية
# ============================================================
def get_accounts_with_foreign_currency(conn=None):
    """جلب الحسابات التي لها حركات بالعملات الأجنبية"""
    base = get_base_currency()
    base_code = (base['code'] if base else 'YER')

    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row
        rows = c.execute("""
            SELECT DISTINCT
                a.id as account_id,
                a.name as account_name,
                a.code as account_code,
                UPPER(TRIM(jl.currency_code)) as currency_code
            FROM journal_lines jl
            JOIN accounts a ON (
                jl.account_id = a.id OR
                jl.account_name = a.name OR
                jl.account_name = a.code
            )
            WHERE jl.currency_code IS NOT NULL
              AND TRIM(jl.currency_code) != ''
              AND UPPER(TRIM(jl.currency_code)) != UPPER(?)
            ORDER BY a.code
        """, (base_code,)).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Error fetching foreign currency accounts: {e}")
        return []
    finally:
        _release_conn(c, owns)


# ============================================================
# حساب الرصيد الأجنبي — ✅ يقبل conn
# ============================================================
def get_foreign_balance(account_id, currency_code, conn=None):
    """
    حساب الرصيد الأجنبي والقيمة المحلية السابقة.
    ✅ يقبل conn=None — يُستخدم من داخل Transaction دون فتح اتصال جديد.
    """
    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row

        acc = c.execute(
            "SELECT name, code FROM accounts WHERE id = ?",
            (account_id,)
        ).fetchone()
        acc_name = acc['name'] if acc else ""
        acc_code = acc['code'] if acc else ""

        row = c.execute("""
            SELECT
                COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) AS foreign_balance,
                COALESCE(SUM(debit * exchange_rate), 0)
              - COALESCE(SUM(credit * exchange_rate), 0) AS local_value
            FROM journal_lines
            WHERE (account_id = ? OR account_name = ? OR account_name = ?)
              AND UPPER(TRIM(currency_code)) = UPPER(TRIM(?))
        """, (account_id, acc_name, acc_code, currency_code)).fetchone()

        foreign_balance = float(row['foreign_balance'] or 0)
        old_local_value = float(row['local_value'] or 0)
        return foreign_balance, old_local_value
    except Exception as e:
        print(f"Error calculating foreign balance: {e}")
        return 0.0, 0.0
    finally:
        _release_conn(c, owns)


# ============================================================
# ✅ مساعد: تحديث رصيد الصندوق/البنك المرتبط بالحساب
# ============================================================
def _update_linked_treasury_balance(account_id, account_code, difference, conn):
    """
    إذا كان الحساب مرتبطاً بصندوق أو بنك → نُحدّث current_balance بالفرق.
    Returns: (updated, source_type, source_name)
    """
    # 1) فحص الصندوق
    row = conn.execute("""
        SELECT id, name, current_balance
        FROM cash_accounts
        WHERE account_code = ? AND is_active = 1
        LIMIT 1
    """, (account_code,)).fetchone()

    if row:
        new_balance = float(row["current_balance"] or 0) + difference
        conn.execute(
            "UPDATE cash_accounts SET current_balance = ? WHERE id = ?",
            (new_balance, row["id"])
        )
        return True, "cash", row["name"]

    # 2) فحص البنك
    row = conn.execute("""
        SELECT id, bank_name, current_balance
        FROM bank_accounts
        WHERE account_code = ? AND is_active = 1
        LIMIT 1
    """, (account_code,)).fetchone()

    if row:
        new_balance = float(row["current_balance"] or 0) + difference
        conn.execute(
            "UPDATE bank_accounts SET current_balance = ? WHERE id = ?",
            (new_balance, row["id"])
        )
        return True, "bank", row["bank_name"]

    return False, None, None


# ============================================================
# تنفيذ إعادة التقييم
# ============================================================
def perform_revaluation(account_id, currency_code, new_rate, revaluation_date,
                        created_by="admin", conn=None):
    """
    تنفيذ عملية إعادة التقييم وإنشاء القيود المحاسبية تلقائياً.
    ✅ يقبل conn=None.
    ✅ يحدّث رصيد الصندوق/البنك إن كان الحساب مرتبطاً بهما.
    ✅ BEGIN IMMEDIATE.
    """
    # --- validation ---
    ok, new_rate, err = _validate_rate(new_rate)
    if not ok:
        return None, err

    ok, revaluation_date = _validate_date(revaluation_date)
    if not ok:
        return None, revaluation_date

    if not currency_code or not str(currency_code).strip():
        return None, "كود العملة مطلوب"
    currency_code = str(currency_code).strip().upper()

    base = get_base_currency()
    base_code = (base['code'] if base else 'YER')

    if currency_code == base_code.upper():
        return None, f"لا يمكن إعادة تقييم العملة الأساسية ({base_code})"

    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row
        if owns:
            c.execute("BEGIN IMMEDIATE")

        # 1) التحقق من الحساب
        acc_info = c.execute(
            "SELECT id, name, code FROM accounts WHERE id = ?",
            (account_id,)
        ).fetchone()
        if not acc_info:
            if owns: c.rollback()
            return None, "الحساب المحدد غير موجود في شجرة الحسابات."

        account_name = acc_info['name']
        account_code = acc_info['code']

        # 2) حساب فروق العملة — من الحسابات الوظيفية
        fx_code = get_functional_account("exchange_difference")
        fx_acc = None
        if fx_code:
            fx_acc = c.execute(
                "SELECT id, name FROM accounts WHERE code = ? LIMIT 1",
                (fx_code,)
            ).fetchone()

        if not fx_acc:
            fx_acc = c.execute("""
                SELECT id, name FROM accounts
                WHERE functional_type = 'exchange_difference'
                LIMIT 1
            """).fetchone()

        if not fx_acc:
            if owns: c.rollback()
            return None, (
                "لم يتم العثور على حساب 'فروق أسعار الصرف'. "
                "تأكد من تحديد النوع الوظيفي (exchange_difference)."
            )

        fx_account_id = fx_acc['id']
        fx_account_name = fx_acc['name']

        # 3) حساب الأرصدة — ✅ نفس الاتصال
        foreign_balance, old_local_value = get_foreign_balance(
            account_id, currency_code, conn=c
        )

        if abs(foreign_balance) < 0.001:
            if owns: c.rollback()
            return None, "الرصيد صفر، لا حاجة لإعادة التقييم."

        new_local_value = round(foreign_balance * new_rate, 2)
        difference = round(new_local_value - old_local_value, 2)

        if abs(difference) < 0.01:
            if owns: c.rollback()
            return None, f"لا يوجد فرق جوهري لسعر صرف {currency_code}."

        # 4) بناء أسطر القيد
        if difference > 0:  # ربح
            lines = [
                {"account_id": account_id, "account_name": account_name,
                 "debit": difference, "credit": 0.0,
                 "currency_code": base_code, "exchange_rate": 1.0},
                {"account_id": fx_account_id, "account_name": fx_account_name,
                 "debit": 0.0, "credit": difference,
                 "currency_code": base_code, "exchange_rate": 1.0},
            ]
        else:  # خسارة
            lines = [
                {"account_id": fx_account_id, "account_name": fx_account_name,
                 "debit": abs(difference), "credit": 0.0,
                 "currency_code": base_code, "exchange_rate": 1.0},
                {"account_id": account_id, "account_name": account_name,
                 "debit": 0.0, "credit": abs(difference),
                 "currency_code": base_code, "exchange_rate": 1.0},
            ]

        desc = f"إعادة تقييم {account_name} - {currency_code} (سعر: {new_rate:,.2f})"

        # 5) حفظ القيد — ✅ نفس الاتصال
        journal_result = save_journal_entry(
            description=desc, lines=lines,
            entry_date=revaluation_date, conn=c
        )

        if isinstance(journal_result, tuple):
            entry_id = journal_result[0]
            error_msg = journal_result[1] if len(journal_result) > 1 else None
            if error_msg:
                if owns: c.rollback()
                return None, f"فشل إنشاء القيد المحاسبي: {error_msg}"
        else:
            entry_id = journal_result

        if not entry_id:
            if owns: c.rollback()
            return None, "تعذر استخراج رقم القيد المحاسبي."

        old_calculated_rate = (
            old_local_value / foreign_balance if foreign_balance != 0 else 0
        )

        # 6) ✅ تحديث رصيد الصندوق/البنك إن وُجد
        updated, source_type, source_name = _update_linked_treasury_balance(
            account_id, account_code, difference, c
        )

        # 7) الحفظ في جدول التقييم
        c.execute("""
            INSERT INTO currency_revaluations
            (date, account_id, account_name, currency_code,
             old_rate, new_rate, foreign_balance,
             old_local_value, new_local_value, difference,
             journal_entry_id, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            revaluation_date, account_id, account_name, currency_code,
            old_calculated_rate, new_rate, foreign_balance,
            old_local_value, new_local_value, difference,
            entry_id, created_by
        ))

        if owns:
            c.commit()

        # 8) التدقيق
        note = f"{account_name} ({currency_code}): فرق {difference:,.2f}"
        if updated:
            note += f" | تم تحديث {source_type} «{source_name}»"

        log_action(
            username=created_by,
            action="إعادة تقييم عملة",
            table_name="currency_revaluations",
            record_id=entry_id,
            new_value=note
        )

        return entry_id, None

    except sqlite3.Error as db_err:
        if owns:
            try: c.rollback()
            except Exception: pass
        return None, f"خطأ قاعدة بيانات: {str(db_err)}"
    except Exception as e:
        if owns:
            try: c.rollback()
            except Exception: pass
        return None, f"خطأ غير متوقع: {str(e)}"
    finally:
        _release_conn(c, owns)


# ============================================================
# سجل العمليات
# ============================================================
def get_revaluation_history(limit=50, conn=None):
    """سجل عمليات إعادة التقييم المنجزة"""
    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row
        rows = c.execute("""
            SELECT * FROM currency_revaluations
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(h) for h in rows]
    except Exception as e:
        print(f"Error fetching revaluation history: {e}")
        return []
    finally:
        _release_conn(c, owns)


# ============================================================
# ✅ تقرير: تأثير التقييم على أرصدة الصندوق/البنك
# ============================================================
def get_treasury_impact_preview(account_id, currency_code, new_rate, conn=None):
    """
    معاينة تأثير إعادة التقييم على أرصدة الصندوق/البنك.
    Returns: {
        foreign_balance, old_local_value, new_local_value, difference,
        treasury_linked: bool, treasury_type: 'cash'|'bank'|None,
        treasury_name: str|None, treasury_old_balance, treasury_new_balance
    }
    """
    ok, new_rate, err = _validate_rate(new_rate)
    if not ok:
        return {"error": err}

    c, owns = _resolve_conn(conn)
    try:
        c.row_factory = sqlite3.Row

        acc = c.execute(
            "SELECT id, name, code FROM accounts WHERE id = ?",
            (account_id,)
        ).fetchone()
        if not acc:
            return {"error": "الحساب غير موجود"}

        foreign_balance, old_local_value = get_foreign_balance(
            account_id, currency_code, conn=c
        )
        new_local_value = round(foreign_balance * new_rate, 2)
        difference = round(new_local_value - old_local_value, 2)

        result = {
            "foreign_balance": foreign_balance,
            "old_local_value": old_local_value,
            "new_local_value": new_local_value,
            "difference": difference,
            "treasury_linked": False,
            "treasury_type": None,
            "treasury_name": None,
            "treasury_old_balance": None,
            "treasury_new_balance": None,
        }

        # فحص الربط
        row = c.execute(
            "SELECT name, current_balance FROM cash_accounts "
            "WHERE account_code = ? AND is_active = 1 LIMIT 1",
            (acc["code"],)
        ).fetchone()
        if row:
            result.update({
                "treasury_linked": True,
                "treasury_type": "cash",
                "treasury_name": row["name"],
                "treasury_old_balance": float(row["current_balance"] or 0),
                "treasury_new_balance": float(row["current_balance"] or 0) + difference,
            })
            return result

        row = c.execute(
            "SELECT bank_name, current_balance FROM bank_accounts "
            "WHERE account_code = ? AND is_active = 1 LIMIT 1",
            (acc["code"],)
        ).fetchone()
        if row:
            result.update({
                "treasury_linked": True,
                "treasury_type": "bank",
                "treasury_name": row["bank_name"],
                "treasury_old_balance": float(row["current_balance"] or 0),
                "treasury_new_balance": float(row["current_balance"] or 0) + difference,
            })

        return result
    finally:
        _release_conn(c, owns)
