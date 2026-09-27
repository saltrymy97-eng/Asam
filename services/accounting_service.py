# services/accounting_service.py - منطق الحسابات وقيود اليومية
# v4.0 — ✅ استخدام Connection Registry + BEGIN IMMEDIATE
import uuid
from datetime import date
from services import cost_center_service
from services.currency_service import get_base_currency, get_exchange_rate
from services.period_service import is_period_closed
from database import get_connection, close_connection


# ✅ إزالة get_conn() المنفصلة — نستخدم Registry
def _resolve_conn(conn):
    if conn is None:
        return get_connection(), True
    return conn, False


def _release_conn(conn, owns):
    """لا نغلق — Registry يُدير الاتصال"""
    if owns:
        close_connection(conn)


def get_account_code(account_input, conn=None):
    """تحويل اسم الحساب أو كوده إلى كود نصي موحد."""
    if account_input is None:
        return None

    account_input = str(account_input).strip()
    if not account_input:
        return None

    if account_input.isdigit():
        return account_input

    c, owns = _resolve_conn(conn)
    try:
        row = c.execute(
            "SELECT code FROM accounts WHERE name = ? OR name LIKE ? OR code = ?",
            (account_input, f"%{account_input}%", account_input)
        ).fetchone()

        if row:
            return row["code"]

        if account_input[0].isdigit():
            code_part = account_input.split("-")[0].strip()
            if code_part.isdigit():
                return code_part

        return None
    finally:
        _release_conn(c, owns)


def _safe_is_period_closed(entry_date, conn):
    """استدعاء آمن لـ is_period_closed"""
    try:
        return is_period_closed(entry_date, conn=conn)
    except TypeError:
        try:
            return is_period_closed(entry_date)
        except Exception:
            return False
    except Exception:
        return False


def save_journal_entry(description, lines, entry_date=None,
                       cost_center_allocations=None, conn=None,
                       skip_period_check=False):
    """
    حفظ قيد يومية جديد.
    ✅ يستخدم Connection Registry عند conn=None.
    ✅ BEGIN IMMEDIATE عند فتح Transaction جديدة.
    """
    if entry_date is None:
        entry_date = date.today().strftime("%Y-%m-%d")

    c, owns = _resolve_conn(conn)
    try:
        if not skip_period_check and _safe_is_period_closed(entry_date, c):
            return None, f"لا يمكن حفظ القيد في فترة مغلقة: {entry_date}. يرجى فتح الفترة أولاً."

        base_currency = get_base_currency()
        base_code = base_currency['code'] if base_currency else 'YER'

        # ✅ BEGIN IMMEDIATE
        if owns:
            c.execute("BEGIN IMMEDIATE")

        reference = f"ENT-{entry_date}-{uuid.uuid4().hex[:8]}"
        cur = c.execute(
            "INSERT INTO journal_entries (date, description, reference) VALUES (?, ?, ?)",
            (entry_date, description, reference)
        )
        entry_id = cur.lastrowid

        line_ids = []
        total_debit_base = 0.0
        total_credit_base = 0.0

        for line in lines:
            if line.get("account"):
                account_name = line["account"]
            else:
                account_name = line.get("account_id")

            if account_name is None:
                if owns:
                    c.execute("ROLLBACK")
                return None, "خطأ: سطر القيد يفتقد إلى معرف الحساب."

            if isinstance(account_name, int) or (
                isinstance(account_name, str) and account_name.isdigit()
            ):
                code = get_account_code(account_name, c)
                if code:
                    account_name = code

            currency_code = line.get("currency_code", base_code)
            debit = float(line.get("debit", 0.0) or 0.0)
            credit = float(line.get("credit", 0.0) or 0.0)

            raw_rate = line.get("exchange_rate")
            exchange_rate = float(raw_rate) if raw_rate not in [None, ""] else 1.0

            if currency_code != base_code and exchange_rate == 1.0:
                fetched_rate = get_exchange_rate(currency_code, base_code, entry_date)
                if fetched_rate:
                    exchange_rate = float(fetched_rate)
                    line['exchange_rate'] = exchange_rate
                else:
                    if owns:
                        c.execute("ROLLBACK")
                    return None, (
                        f"لم يتم العثور على سعر صرف للعملة "
                        f"{currency_code} بتاريخ {entry_date}."
                    )

            if currency_code != base_code:
                debit_base = debit * exchange_rate
                credit_base = credit * exchange_rate
            else:
                debit_base = debit
                credit_base = credit

            total_debit_base += debit_base
            total_credit_base += credit_base

            cur_line = c.execute(
                "INSERT INTO journal_lines "
                "(entry_id, account_name, debit, credit, currency_code, exchange_rate) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (entry_id, account_name, debit, credit, currency_code, exchange_rate)
            )
            line_ids.append(cur_line.lastrowid)

        if round(abs(total_debit_base - total_credit_base), 2) > 0.01:
            if owns:
                c.execute("ROLLBACK")
            return None, (
                f"القيد غير متوازن! "
                f"المدين الأساسي: {total_debit_base:,.2f} ، "
                f"الدائن الأساسي: {total_credit_base:,.2f}"
            )

        if cost_center_allocations:
            for alloc_entry in cost_center_allocations:
                line_index = alloc_entry.get('line_index', 0)
                if line_index < len(line_ids):
                    journal_line_id = line_ids[line_index]
                    allocations = alloc_entry.get('allocations', [])
                    if allocations:
                        cost_center_service.allocate_journal_line(
                            journal_line_id, allocations
                        )

        if owns:
            c.commit()
        return entry_id, None

    except Exception as e:
        if owns:
            try:
                c.execute("ROLLBACK")
            except Exception:
                pass
        return None, str(e)
    finally:
        _release_conn(c, owns)


def update_journal_entry(entry_id, description, lines, entry_date=None,
                         cost_center_allocations=None, conn=None):
    """تحديث قيد موجود"""
    if entry_date is None:
        entry_date = date.today().strftime("%Y-%m-%d")

    c, owns = _resolve_conn(conn)
    try:
        if _safe_is_period_closed(entry_date, c):
            return False, f"لا يمكن تحديث قيد في فترة مغلقة: {entry_date}."

        base_currency = get_base_currency()
        base_code = base_currency['code'] if base_currency else 'YER'

        if owns:
            c.execute("BEGIN IMMEDIATE")

        c.execute(
            "UPDATE journal_entries SET date = ?, description = ? WHERE id = ?",
            (entry_date, description, entry_id)
        )
        old_lines = c.execute(
            "SELECT id FROM journal_lines WHERE entry_id = ?", (entry_id,)
        ).fetchall()
        for ol in old_lines:
            c.execute(
                "DELETE FROM cost_center_allocations WHERE journal_line_id = ?",
                (ol['id'],)
            )
        c.execute("DELETE FROM journal_lines WHERE entry_id = ?", (entry_id,))

        line_ids = []
        total_debit_base = 0.0
        total_credit_base = 0.0

        for line in lines:
            if line.get("account"):
                account_name = line["account"]
            else:
                account_name = line.get("account_id")

            if account_name is None:
                if owns:
                    c.execute("ROLLBACK")
                return False, "خطأ: سطر القيد يفتقد إلى معرف الحساب."

            if isinstance(account_name, int) or (
                isinstance(account_name, str) and account_name.isdigit()
            ):
                code = get_account_code(account_name, c)
                if code:
                    account_name = code

            currency_code = line.get("currency_code", base_code)
            debit = float(line.get("debit", 0.0) or 0.0)
            credit = float(line.get("credit", 0.0) or 0.0)

            raw_rate = line.get("exchange_rate")
            exchange_rate = float(raw_rate) if raw_rate not in [None, ""] else 1.0

            if currency_code != base_code and exchange_rate == 1.0:
                fetched_rate = get_exchange_rate(currency_code, base_code, entry_date)
                if fetched_rate:
                    exchange_rate = float(fetched_rate)
                    line['exchange_rate'] = exchange_rate
                else:
                    if owns:
                        c.execute("ROLLBACK")
                    return False, (
                        f"لم يتم العثور على سعر صرف للعملة "
                        f"{currency_code} بتاريخ {entry_date}."
                    )

            if currency_code != base_code:
                debit_base = debit * exchange_rate
                credit_base = credit * exchange_rate
            else:
                debit_base = debit
                credit_base = credit

            total_debit_base += debit_base
            total_credit_base += credit_base

            cur_line = c.execute(
                "INSERT INTO journal_lines "
                "(entry_id, account_name, debit, credit, currency_code, exchange_rate) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (entry_id, account_name, debit, credit, currency_code, exchange_rate)
            )
            line_ids.append(cur_line.lastrowid)

        if round(abs(total_debit_base - total_credit_base), 2) > 0.01:
            if owns:
                c.execute("ROLLBACK")
            return False, (
                f"القيد غير متوازن! "
                f"المدين الأساسي: {total_debit_base:,.2f} ، "
                f"الدائن الأساسي: {total_credit_base:,.2f}"
            )

        if cost_center_allocations:
            for alloc_entry in cost_center_allocations:
                line_index = alloc_entry.get('line_index', 0)
                if line_index < len(line_ids):
                    journal_line_id = line_ids[line_index]
                    allocations = alloc_entry.get('allocations', [])
                    if allocations:
                        cost_center_service.allocate_journal_line(
                            journal_line_id, allocations
                        )

        if owns:
            c.commit()
        return True, None

    except Exception as e:
        if owns:
            try:
                c.execute("ROLLBACK")
            except Exception:
                pass
        return False, str(e)
    finally:
        _release_conn(c, owns)


# ============================================================
# دوال القراءة — ✅ Registry
# ============================================================
def get_recent_entries(limit=10, conn=None):
    c, owns = _resolve_conn(conn)
    try:
        entries = c.execute(
            "SELECT id, date, description, reference FROM journal_entries "
            "ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(e) for e in entries]
    finally:
        _release_conn(c, owns)


def get_entry_details(entry_id, conn=None):
    c, owns = _resolve_conn(conn)
    try:
        lines = c.execute(
            "SELECT id, account_name, debit, credit, currency_code, exchange_rate "
            "FROM journal_lines WHERE entry_id = ?", (entry_id,)
        ).fetchall()
        result = []
        for l in lines:
            line_dict = dict(l)
            allocations = c.execute("""
                SELECT cca.id, cca.cost_center_id, cc.name as center_name,
                       cc.code as center_code, cca.amount, cca.percentage
                FROM cost_center_allocations cca
                JOIN cost_centers cc ON cca.cost_center_id = cc.id
                WHERE cca.journal_line_id = ?
            """, (l['id'],)).fetchall()
            line_dict['cost_center_allocations'] = (
                [dict(a) for a in allocations] if allocations else []
            )
            result.append(line_dict)
        return result
    finally:
        _release_conn(c, owns)


def get_ledger(account_name, conn=None):
    c, owns = _resolve_conn(conn)
    try:
        ledger = c.execute("""
            SELECT je.date, je.description, jl.debit, jl.credit,
                   jl.currency_code, jl.exchange_rate
            FROM journal_lines jl
            JOIN journal_entries je ON jl.entry_id = je.id
            WHERE jl.account_name = ?
            ORDER BY je.date, je.id
        """, (account_name,)).fetchall()
        return [dict(l) for l in ledger]
    finally:
        _release_conn(c, owns)


def get_trial_balance(conn=None):
    c, owns = _resolve_conn(conn)
    try:
        tb = c.execute("""
            SELECT account_name,
                   SUM(debit * exchange_rate) as total_debit,
                   SUM(credit * exchange_rate) as total_credit
            FROM journal_lines
            GROUP BY account_name
            ORDER BY account_name
        """).fetchall()
        return [dict(t) for t in tb]
    finally:
        _release_conn(c, owns)


def get_distinct_accounts(conn=None):
    c, owns = _resolve_conn(conn)
    try:
        accounts = c.execute(
            "SELECT DISTINCT account_name FROM journal_lines ORDER BY account_name"
        ).fetchall()
        return [a["account_name"] for a in accounts]
    finally:
        _release_conn(c, owns)


def get_entry_with_allocations(entry_id):
    return cost_center_service.get_allocations_for_entry(entry_id)
