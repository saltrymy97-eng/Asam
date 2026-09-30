# services/accounting_service.py - منطق الحسابات وقيود اليومية
# v4.2 — ✅ Connection Registry + BEGIN IMMEDIATE
# ✅ تسجيل تدقيق كامل + قراءة تلقائية للمستخدم من session_state
import uuid
from datetime import date
from services import cost_center_service
from services.currency_service import get_base_currency, get_exchange_rate
from services.period_service import is_period_closed
from services.audit_service import log_action
from database import get_connection, close_connection


def _resolve_conn(conn):
    if conn is None:
        return get_connection(), True
    return conn, False


def _release_conn(conn, owns):
    """لا نغلق — Registry يُدير الاتصال"""
    if owns:
        close_connection(conn)


# ============================================================
# ✅ دالة مساعدة: جلب اسم المستخدم الحالي
# ============================================================
def _get_current_user(default="system"):
    """
    جلب اسم المستخدم الحالي من session_state بأمان.
    - يُعيد default إذا لم يوجد session أو مستخدم
    """
    try:
        import streamlit as st
        user = st.session_state.get('user') or {}
        username = user.get('username')
        if username:
            return username
    except Exception:
        pass
    return default


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


# ============================================================
# ✅ دالة مساعدة: تجهيز ملخص القيد لسجل التدقيق
# ============================================================
def _summarize_entry(description, entry_date, lines, entry_id,
                     total_debit, total_credit):
    """تجهيز dict ملخص القيد لسجل التدقيق"""
    accounts_used = []
    for line in lines:
        acc = line.get("account") or line.get("account_id")
        if acc:
            accounts_used.append(str(acc))

    return {
        "entry_id": entry_id,
        "description": description,
        "date": entry_date,
        "lines_count": len(lines),
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "accounts": accounts_used,
    }


# ============================================================
# ✅ دالة مساعدة: جلب لقطة كاملة للقيد
# ============================================================
def _snapshot_entry(entry_id, conn):
    """جلب بيانات قيد كامل (لحفظها في old_value عند الحذف/التعديل)"""
    try:
        entry = conn.execute(
            "SELECT id, date, description, reference FROM journal_entries WHERE id = ?",
            (entry_id,)
        ).fetchone()
        if not entry:
            return None

        entry_dict = dict(entry)

        lines = conn.execute(
            "SELECT account_name, debit, credit, currency_code, exchange_rate "
            "FROM journal_lines WHERE entry_id = ?",
            (entry_id,)
        ).fetchall()

        entry_dict["lines"] = [dict(l) for l in lines]
        return entry_dict
    except Exception:
        return None


# ============================================================
# إنشاء قيد جديد
# ============================================================
def save_journal_entry(description, lines, entry_date=None,
                       cost_center_allocations=None, conn=None,
                       skip_period_check=False, created_by=None):
    """
    حفظ قيد يومية جديد.
    ✅ v4.2: يسجّل القيد في سجل التدقيق تلقائياً.
    ✅ v4.2: يقرأ اسم المستخدم من session_state إذا لم يُمرَّر.
    """
    if entry_date is None:
        entry_date = date.today().strftime("%Y-%m-%d")

    # ✅ قراءة تلقائية للمستخدم
    if created_by is None:
        created_by = _get_current_user()

    c, owns = _resolve_conn(conn)
    try:
        if not skip_period_check and _safe_is_period_closed(entry_date, c):
            return None, (
                f"لا يمكن حفظ القيد في فترة مغلقة: {entry_date}. "
                f"يرجى فتح الفترة أولاً."
            )

        base_currency = get_base_currency()
        base_code = base_currency['code'] if base_currency else 'YER'

        if owns:
            c.execute("BEGIN IMMEDIATE")

        reference = f"ENT-{entry_date}-{uuid.uuid4().hex[:8]}"
        cur = c.execute(
            "INSERT INTO journal_entries (date, description, reference) "
            "VALUES (?, ?, ?)",
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
                "(entry_id, account_name, debit, credit, "
                "currency_code, exchange_rate) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (entry_id, account_name, debit, credit,
                 currency_code, exchange_rate)
            )
            line_ids.append(cur_line.lastrowid)

        # ✅ فحص التوازن
        if round(abs(total_debit_base - total_credit_base), 2) > 0.01:
            if owns:
                c.execute("ROLLBACK")
            return None, (
                f"القيد غير متوازن! "
                f"المدين الأساسي: {total_debit_base:,.2f} ، "
                f"الدائن الأساسي: {total_credit_base:,.2f}"
            )

        # ✅ توزيعات مراكز التكلفة
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

        # ============================================================
        # ✅ تسجيل القيد في سجل التدقيق
        # ============================================================
        try:
            summary = _summarize_entry(
                description=description,
                entry_date=entry_date,
                lines=lines,
                entry_id=entry_id,
                total_debit=total_debit_base,
                total_credit=total_credit_base,
            )
            log_action(
                username=created_by,
                action="📝 إنشاء قيد محاسبي",
                table_name="journal_entries",
                record_id=entry_id,
                new_value=summary,
                conn=c,
                commit_now=False,
            )
        except Exception as e:
            print(f"⚠️ فشل تسجيل القيد في سجل التدقيق: {e}")

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


# ============================================================
# تحديث قيد موجود
# ============================================================
def update_journal_entry(entry_id, description, lines, entry_date=None,
                         cost_center_allocations=None, conn=None,
                         updated_by=None):
    """
    تحديث قيد موجود.
    ✅ v4.2: يسجّل old_value + new_value في سجل التدقيق.
    ✅ v4.2: يقرأ اسم المستخدم من session_state إذا لم يُمرَّر.
    """
    if entry_date is None:
        entry_date = date.today().strftime("%Y-%m-%d")

    # ✅ قراءة تلقائية للمستخدم
    if updated_by is None:
        updated_by = _get_current_user()

    c, owns = _resolve_conn(conn)
    try:
        if _safe_is_period_closed(entry_date, c):
            return False, f"لا يمكن تحديث قيد في فترة مغلقة: {entry_date}."

        base_currency = get_base_currency()
        base_code = base_currency['code'] if base_currency else 'YER'

        if owns:
            c.execute("BEGIN IMMEDIATE")

        # ✅ 1. خذ لقطة للقيد القديم قبل التعديل
        old_snapshot = _snapshot_entry(entry_id, c)

        # 2. تحديث رأس القيد
        c.execute(
            "UPDATE journal_entries SET date = ?, description = ? WHERE id = ?",
            (entry_date, description, entry_id)
        )

        # 3. حذف السطور القديمة + توزيعاتها
        old_lines = c.execute(
            "SELECT id FROM journal_lines WHERE entry_id = ?", (entry_id,)
        ).fetchall()
        for ol in old_lines:
            c.execute(
                "DELETE FROM cost_center_allocations WHERE journal_line_id = ?",
                (ol['id'],)
            )
        c.execute("DELETE FROM journal_lines WHERE entry_id = ?", (entry_id,))

        # 4. إدخال السطور الجديدة
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
                "(entry_id, account_name, debit, credit, "
                "currency_code, exchange_rate) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (entry_id, account_name, debit, credit,
                 currency_code, exchange_rate)
            )
            line_ids.append(cur_line.lastrowid)

        # ✅ فحص التوازن
        if round(abs(total_debit_base - total_credit_base), 2) > 0.01:
            if owns:
                c.execute("ROLLBACK")
            return False, (
                f"القيد غير متوازن! "
                f"المدين الأساسي: {total_debit_base:,.2f} ، "
                f"الدائن الأساسي: {total_credit_base:,.2f}"
            )

        # ✅ توزيعات مراكز التكلفة
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

        # ============================================================
        # ✅ تسجيل التحديث في سجل التدقيق
        # ============================================================
        try:
            new_summary = _summarize_entry(
                description=description,
                entry_date=entry_date,
                lines=lines,
                entry_id=entry_id,
                total_debit=total_debit_base,
                total_credit=total_credit_base,
            )
            log_action(
                username=updated_by,
                action="✏️ تعديل قيد محاسبي",
                table_name="journal_entries",
                record_id=entry_id,
                old_value=old_snapshot,
                new_value=new_summary,
                conn=c,
                commit_now=False,
            )
        except Exception as e:
            print(f"⚠️ فشل تسجيل تعديل القيد: {e}")

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
# ✅ حذف قيد محاسبي
# ============================================================
def delete_journal_entry(entry_id, conn=None, deleted_by=None):
    """
    حذف قيد محاسبي مع تسجيل كامل في سجل التدقيق.
    ✅ v4.2: تسجيل كامل قبل الحذف (old_value).
    ✅ v4.2: يقرأ اسم المستخدم من session_state إذا لم يُمرَّر.
    """
    # ✅ قراءة تلقائية للمستخدم
    if deleted_by is None:
        deleted_by = _get_current_user()

    c, owns = _resolve_conn(conn)
    try:
        # 1. جلب لقطة القيد قبل الحذف
        old_snapshot = _snapshot_entry(entry_id, c)
        if not old_snapshot:
            return False, "القيد غير موجود."

        # 2. فحص الفترة المغلقة
        entry_date = old_snapshot.get("date")
        if entry_date and _safe_is_period_closed(entry_date, c):
            return False, (
                f"لا يمكن حذف قيد في فترة مغلقة: {entry_date}. "
                f"يرجى فتح الفترة أولاً."
            )

        if owns:
            c.execute("BEGIN IMMEDIATE")

        # 3. حذف توزيعات مراكز التكلفة
        try:
            c.execute(
                "DELETE FROM cost_center_allocations "
                "WHERE journal_line_id IN "
                "(SELECT id FROM journal_lines WHERE entry_id = ?)",
                (entry_id,)
            )
        except Exception:
            pass

        # 4. حذف السطور ثم القيد
        c.execute("DELETE FROM journal_lines WHERE entry_id = ?", (entry_id,))
        c.execute("DELETE FROM journal_entries WHERE id = ?", (entry_id,))

        # ============================================================
        # ✅ تسجيل الحذف في سجل التدقيق
        # ============================================================
        try:
            log_action(
                username=deleted_by,
                action="🗑️ حذف قيد محاسبي",
                table_name="journal_entries",
                record_id=entry_id,
                old_value=old_snapshot,
                new_value=(
                    f"تم حذف القيد: "
                    f"{old_snapshot.get('description', '')}"
                ),
                conn=c,
                commit_now=False,
            )
        except Exception as e:
            print(f"⚠️ فشل تسجيل حذف القيد: {e}")

        if owns:
            c.commit()
        return True, "تم حذف القيد بنجاح."

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
# دوال القراءة — Registry
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
            "SELECT id, account_name, debit, credit, "
            "currency_code, exchange_rate "
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
            "SELECT DISTINCT account_name FROM journal_lines "
            "ORDER BY account_name"
        ).fetchall()
        return [a["account_name"] for a in accounts]
    finally:
        _release_conn(c, owns)


def get_entry_with_allocations(entry_id):
    return cost_center_service.get_allocations_for_entry(entry_id)
