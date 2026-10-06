# services/bank_service.py – منطق التعاملات البنكية (v9.1)
# 🔧 v9.1 — تصحيحات بعد المراجعة:
#   ✅ توحيد return value في transfer_funds لجميع الحالات → (journal_id, error)
#   ✅ رفض الحساب بدون currency_code (لا افتراض YER)
#   ✅ contra_account_code عاد اختياريًا (لتجنّب كسر الاستدعاءات القديمة)
#   ✅ تصحيح استدعاء cash→cash ليُعيد journal_id وليس True

import sqlite3
from datetime import date, datetime
from database import get_connection, close_connection
from services.currency_service import get_base_currency, get_exchange_rate, convert_amount
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry


# ============================================================
# 🔧 v9.1: قراءة العملة بشكل آمن — رفض الفارغ
# ============================================================
def _require_currency(acc, kind_label):
    """يرفع خطأ إذا كانت العملة مفقودة أو فارغة."""
    curr = (acc or {}).get('currency_code')
    if not curr or not str(curr).strip():
        name = (acc or {}).get('bank_name') or (acc or {}).get('name') or '?'
        raise ValueError(
            f"الحساب {kind_label} '{name}' لا يحتوي على currency_code. "
            f"راجع إعداد الحساب — لا يمكن التحويل بدون عملة محددة."
        )
    return str(curr).strip()


# ============================================================
# دالة مساعدة — توليد transfer_reference موحّد
# ============================================================
def _generate_transfer_reference(conn):
    """TR-YYYYMMDD-NNNN"""
    today = date.today().strftime("%Y%m%d")
    prefix = f"TR-{today}-"

    max_num = 0
    for table in ('bank_transactions', 'cash_transactions'):
        try:
            row = conn.execute(
                f"SELECT reference FROM {table} "
                f"WHERE reference LIKE ? "
                f"ORDER BY reference DESC LIMIT 1",
                (prefix + "%",)
            ).fetchone()
            if row and row[0]:
                try:
                    n = int(str(row[0]).split('-')[-1])
                    if n > max_num:
                        max_num = n
                except (ValueError, IndexError):
                    pass
        except Exception:
            pass

    return f"{prefix}{max_num + 1:04d}"


def _reference_exists(conn, reference):
    """فحص إن كان transfer_reference مستخدمًا من قبل."""
    if not reference:
        return False
    for table in ('bank_transactions', 'cash_transactions'):
        try:
            row = conn.execute(
                f"SELECT 1 FROM {table} WHERE reference = ? LIMIT 1",
                (reference,)
            ).fetchone()
            if row:
                return True
        except Exception:
            pass
    return False


def _require_account_code(acc, kind_label):
    """رفض الحساب بدون account_code — منع fallback للحساب الأب."""
    code = (acc or {}).get('account_code')
    if not code or not str(code).strip():
        name = (acc or {}).get('bank_name') or (acc or {}).get('name') or '?'
        raise ValueError(
            f"الحساب {kind_label} '{name}' لا يحتوي على account_code. "
            f"لا يُسمح بالتحويل على الحساب الأب (1101/1102)."
        )
    return str(code).strip()


# ============================================================
# توليد كود فريد للبنك — MAX+1
# ============================================================
def _generate_unique_bank_code(conn):
    """1102.01, 1102.02, ... — باستخدام MAX+1"""
    parent = conn.execute("""
        SELECT id, code, level FROM accounts
        WHERE functional_type = 'bank' AND is_active = 1
        ORDER BY LENGTH(code), code
        LIMIT 1
    """).fetchone()

    if not parent:
        raise ValueError(
            "حساب البنك الأب مفقود في شجرة الحسابات. "
            "أضف حساباً بالنوع الوظيفي 'bank' أولاً."
        )

    parent_code = parent["code"]
    parent_id = parent["id"]
    parent_level = parent["level"]

    prefix = parent_code + "."
    rows = conn.execute(
        "SELECT code FROM accounts WHERE code LIKE ?", (prefix + "%",)
    ).fetchall()

    max_suffix = 0
    for r in rows:
        try:
            suffix = int(str(r["code"]).split('.')[-1])
            if suffix > max_suffix:
                max_suffix = suffix
        except (ValueError, IndexError):
            continue

    new_code = f"{parent_code}.{max_suffix + 1:02d}"

    return {
        "parent_id": parent_id,
        "parent_code": parent_code,
        "parent_level": parent_level,
        "new_code": new_code,
    }


def _create_system_account(conn, code, name, parent_id, parent_level,
                           functional_type='bank'):
    conn.execute("""
        INSERT INTO accounts
        (code, name, parent_id, level, is_debit, is_active,
         account_type, functional_type, is_system)
        VALUES (?, ?, ?, ?, 'debit', 1, 'Asset', ?, 1)
    """, (code, name, parent_id, parent_level + 1, functional_type))


# ============================================================
# فحص كفاية الرصيد
# ============================================================
def check_bank_sufficient_balance(bank_account_id, amount, conn=None):
    if bank_account_id is None:
        return False, "معرف الحساب البنكي مفقود"

    try:
        amount_float = float(amount)
    except (ValueError, TypeError):
        return False, "المبلغ غير صحيح"

    if amount_float <= 0:
        return False, "المبلغ يجب أن يكون أكبر من صفر"

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        row = conn.execute(
            "SELECT bank_name, current_balance FROM bank_accounts WHERE id = ? AND is_active = 1",
            (bank_account_id,)
        ).fetchone()

        if not row:
            return False, "الحساب البنكي غير موجود أو غير نشط"

        current = float(row["current_balance"] or 0)
        if current < -0.001:
            return False, (
                f"رصيد البنك '{row['bank_name']}' سالب ({current:,.2f}) "
                f"- راجع الحركات السابقة"
            )
        if amount_float > current + 0.001:
            return False, (
                f"الرصيد غير كافٍ في '{row['bank_name']}'. "
                f"المتاح: {current:,.2f}، المطلوب: {amount_float:,.2f}"
            )
        return True, None
    finally:
        if own_conn:
            close_connection(conn)


# ===================== إدارة الحسابات البنكية =====================

def create_bank_account(bank_name, account_number, account_name="",
                        currency_code="YER", opening_balance=0.0,
                        account_code=None, conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN IMMEDIATE")

        if account_code:
            final_account_code = account_code
        else:
            code_info = _generate_unique_bank_code(conn)
            final_account_code = code_info["new_code"]

            _create_system_account(
                conn,
                code=final_account_code,
                name=bank_name,
                parent_id=code_info["parent_id"],
                parent_level=code_info["parent_level"],
                functional_type='bank',
            )

        capital_account_code = None
        if opening_balance > 0:
            capital_account_code = get_functional_account("capital")
            if not capital_account_code:
                raise ValueError(
                    "حساب رأس المال مفقود في شجرة الحسابات. "
                    "أضف حساباً بالنوع الوظيفي 'capital' أولاً."
                )

        conn.execute(
            """INSERT INTO bank_accounts 
               (bank_name, account_number, account_name, currency_code, 
                opening_balance, current_balance, account_code)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (bank_name, account_number, account_name, currency_code,
             opening_balance, opening_balance, final_account_code)
        )

        if opening_balance > 0:
            lines = [
                {
                    "account": final_account_code,
                    "debit": opening_balance,
                    "credit": 0.0,
                    "currency_code": currency_code,
                    "exchange_rate": 1.0
                },
                {
                    "account": capital_account_code,
                    "debit": 0.0,
                    "credit": opening_balance,
                    "currency_code": currency_code,
                    "exchange_rate": 1.0
                }
            ]

            _entry_id, jerr = save_journal_entry(
                description=f"رصيد افتتاحي لحساب بنكي {bank_name} ({account_number})",
                lines=lines,
                entry_date=date.today().strftime("%Y-%m-%d"),
                conn=conn,
                skip_period_check=True
            )
            if jerr:
                raise ValueError(f"فشل القيد الافتتاحي: {jerr}")

        if own_conn:
            conn.commit()

        return True

    except Exception as e:
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise e
    finally:
        if own_conn:
            close_connection(conn)


def update_bank_account(account_id, bank_name=None, account_number=None,
                        account_name=None, currency_code=None,
                        account_code=None, is_active=None, conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    fields = []
    values = []
    if bank_name:
        fields.append("bank_name = ?")
        values.append(bank_name)
    if account_number:
        fields.append("account_number = ?")
        values.append(account_number)
    if account_name:
        fields.append("account_name = ?")
        values.append(account_name)
    if currency_code:
        fields.append("currency_code = ?")
        values.append(currency_code)
    if account_code:
        fields.append("account_code = ?")
        values.append(account_code)
    if is_active is not None:
        fields.append("is_active = ?")
        values.append(1 if is_active else 0)

    if not fields:
        if own_conn:
            close_connection(conn)
        return

    try:
        if own_conn:
            conn.execute("BEGIN IMMEDIATE")
        values.append(account_id)
        conn.execute(f"UPDATE bank_accounts SET {', '.join(fields)} WHERE id = ?", values)
        if own_conn:
            conn.commit()
    except Exception as e:
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise e
    finally:
        if own_conn:
            close_connection(conn)


def get_all_bank_accounts(active_only=True, conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        query = "SELECT * FROM bank_accounts"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY bank_name"
        rows = conn.execute(query).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            close_connection(conn)


def get_bank_account_by_id(account_id, conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        row = conn.execute(
            "SELECT * FROM bank_accounts WHERE id = ?", (account_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        if own_conn:
            close_connection(conn)


def get_bank_account_by_code(account_code, conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        row = conn.execute(
            "SELECT * FROM bank_accounts WHERE account_code = ? AND is_active = 1",
            (account_code,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        if own_conn:
            close_connection(conn)


def update_bank_balance(account_id, conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN IMMEDIATE")

        conn.execute("""
            UPDATE bank_accounts
            SET current_balance = opening_balance + COALESCE((
                SELECT SUM(CASE 
                    WHEN type IN ('deposit','transfer_in') THEN amount 
                    ELSE -amount 
                END)
                FROM bank_transactions
                WHERE bank_account_id = ?
            ), 0)
            WHERE id = ?
        """, (account_id, account_id))

        row = conn.execute(
            "SELECT current_balance FROM bank_accounts WHERE id = ?",
            (account_id,)
        ).fetchone()
        new_balance = float(row["current_balance"] or 0) if row else 0.0

        if own_conn:
            conn.commit()
        return new_balance

    except Exception as e:
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise e
    finally:
        if own_conn:
            close_connection(conn)


# ===================== الحركات البنكية =====================

def add_bank_transaction(bank_account_id, transaction_date, description,
                         trans_type, amount, reference="",
                         contra_account_code=None, conn=None,
                         skip_balance_check=False):
    """
    إضافة حركة بنكية مع قيد تلقائي.
    ⚠️ للحركات المستقلة (إيداع/سحب يدوي) — التحويلات لا تمر من هنا.
    """
    if trans_type not in ('deposit', 'withdrawal', 'transfer_in', 'transfer_out'):
        raise ValueError("نوع الحركة غير صالح")

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValueError("المبلغ غير صحيح")

    if amount <= 0:
        raise ValueError("المبلغ يجب أن يكون أكبر من صفر")

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN IMMEDIATE")

        bank_acc = get_bank_account_by_id(bank_account_id, conn=conn)
        if not bank_acc:
            raise ValueError("الحساب البنكي غير موجود")

        bank_account_code = _require_account_code(bank_acc, "البنكي")
        currency = _require_currency(bank_acc, "البنكي")

        if trans_type in ('withdrawal', 'transfer_out') and not skip_balance_check:
            ok, err = check_bank_sufficient_balance(bank_account_id, amount, conn=conn)
            if not ok:
                if own_conn:
                    conn.rollback()
                raise ValueError(err)

        base_currency = get_base_currency()
        if currency == base_currency['code']:
            exchange_rate = 1.0
        else:
            exchange_rate = get_exchange_rate(currency, base_currency['code']) or 1.0

        # 🔧 v9.1: contra اختياري — يحذّر بدل أن يرفض
        if not contra_account_code:
            # ملاحظة: التحويلات لا تمر من هنا. هذا للحركات اليدوية فقط.
            # لو استُدعيت بدون contra، نستخدم الحساب الوظيفي "cash" كطرف مقابل.
            contra_account_code = get_functional_account("cash")
            if not contra_account_code:
                raise ValueError(
                    "لم يُمرَّر contra_account_code ولا يوجد حساب وظيفي 'cash'."
                )

        lines = []
        if trans_type in ('deposit', 'transfer_in'):
            lines.append({
                "account": bank_account_code,
                "debit": amount,
                "credit": 0.0,
                "currency_code": currency,
                "exchange_rate": exchange_rate
            })
            lines.append({
                "account": contra_account_code,
                "debit": 0.0,
                "credit": amount,
                "currency_code": currency,
                "exchange_rate": exchange_rate
            })
        else:
            lines.append({
                "account": contra_account_code,
                "debit": amount,
                "credit": 0.0,
                "currency_code": currency,
                "exchange_rate": exchange_rate
            })
            lines.append({
                "account": bank_account_code,
                "debit": 0.0,
                "credit": amount,
                "currency_code": currency,
                "exchange_rate": exchange_rate
            })

        journal_id, jerr = save_journal_entry(
            entry_date=transaction_date,
            description=f"{description} ({reference})".strip(),
            lines=lines,
            conn=conn,
            skip_period_check=False
        )
        if jerr:
            if own_conn:
                conn.rollback()
            raise ValueError(f"فشل القيد: {jerr}")

        reconciled_flag = 1 if journal_id else 0
        conn.execute(
            """INSERT INTO bank_transactions 
               (bank_account_id, transaction_date, description, type, amount, 
                reference, reconciled, journal_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (bank_account_id, transaction_date, description, trans_type,
             amount, reference, reconciled_flag, journal_id)
        )

        update_bank_balance(bank_account_id, conn=conn)

        if own_conn:
            conn.commit()

        return True
    except Exception as e:
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise e
    finally:
        if own_conn:
            close_connection(conn)


# ============================================================
# transfer_between_banks — قيد واحد + حركتان مباشرتان
# ============================================================
def transfer_between_banks(from_account_id, to_account_id, amount,
                            transfer_date, description="تحويل بين حسابات بنكية",
                            reference="", conn=None):
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValueError("المبلغ غير صحيح")

    if amount <= 0:
        raise ValueError("المبلغ يجب أن يكون أكبر من صفر")

    if from_account_id == to_account_id:
        raise ValueError("لا يمكن التحويل لنفس الحساب")

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN IMMEDIATE")

        from_acc = get_bank_account_by_id(from_account_id, conn=conn)
        to_acc = get_bank_account_by_id(to_account_id, conn=conn)

        if not from_acc or not to_acc:
            raise ValueError("أحد الحسابات البنكية غير موجود")

        if not from_acc.get('is_active', 1) or not to_acc.get('is_active', 1):
            raise ValueError("أحد الحسابات البنكية غير نشط")

        from_code = _require_account_code(from_acc, "البنكي المصدر")
        to_code = _require_account_code(to_acc, "البنكي الوجهة")

        # 🔧 v9.1: رفض العملة الفارغة
        from_curr = _require_currency(from_acc, "البنكي المصدر")
        to_curr = _require_currency(to_acc, "البنكي الوجهة")

        if from_curr != to_curr:
            raise ValueError(
                f"لا يمكن تحويل الأموال بين حسابين بعملتين مختلفتين حاليًا. "
                f"المصدر: {from_curr} — الوجهة: {to_curr}."
            )

        ok, err = check_bank_sufficient_balance(from_account_id, amount, conn=conn)
        if not ok:
            raise ValueError(err)

        if not reference:
            reference = _generate_transfer_reference(conn)

        if _reference_exists(conn, reference):
            raise ValueError(
                f"مرجع التحويل '{reference}' مستخدم مسبقًا. "
                f"لا يمكن تنفيذ التحويل مرتين."
            )

        lines = [
            {
                "account": to_code,
                "debit": amount,
                "credit": 0.0,
                "currency_code": to_curr,
                "exchange_rate": 1.0
            },
            {
                "account": from_code,
                "debit": 0.0,
                "credit": amount,
                "currency_code": from_curr,
                "exchange_rate": 1.0
            }
        ]

        journal_id, jerr = save_journal_entry(
            entry_date=transfer_date,
            description=f"{description} من {from_acc['bank_name']} إلى {to_acc['bank_name']}",
            lines=lines,
            conn=conn,
            skip_period_check=False
        )
        if jerr:
            raise ValueError(f"فشل القيد: {jerr}")

        conn.execute(
            """INSERT INTO bank_transactions 
               (bank_account_id, transaction_date, description, type, amount,
                reference, reconciled, journal_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (from_account_id, transfer_date,
             f"تحويل إلى {to_acc['bank_name']}", 'transfer_out',
             amount, reference, 1, journal_id)
        )
        conn.execute(
            """INSERT INTO bank_transactions 
               (bank_account_id, transaction_date, description, type, amount,
                reference, reconciled, journal_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (to_account_id, transfer_date,
             f"تحويل من {from_acc['bank_name']}", 'transfer_in',
             amount, reference, 1, journal_id)
        )

        update_bank_balance(from_account_id, conn=conn)
        update_bank_balance(to_account_id, conn=conn)

        if own_conn:
            conn.commit()

        return journal_id
    except Exception as e:
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise e
    finally:
        if own_conn:
            close_connection(conn)


# ============================================================
# 🔧 v9.1: transfer_funds — توحيد return value في كل الحالات
# ============================================================
def transfer_funds(from_kind, from_id, to_kind, to_id, amount,
                   transfer_date, description="تحويل", reference="",
                   conn=None):
    """
    تحويل موحّد بين أي حسابين (بنك/صندوق).
    ✅ يُعيد دائمًا (journal_id, error):
        - نجاح: (journal_id, None)
        - فشل:  (None, "رسالة الخطأ")
    """
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return None, "المبلغ غير صحيح"

    if amount <= 0:
        return None, "المبلغ يجب أن يكون أكبر من صفر"

    if from_kind == to_kind and from_id == to_id:
        return None, "لا يمكن التحويل لنفس الحساب"

    if from_kind not in ('bank', 'cash') or to_kind not in ('bank', 'cash'):
        return None, "نوع الحساب غير صالح"

    # ── bank → bank ──
    if from_kind == 'bank' and to_kind == 'bank':
        try:
            journal_id = transfer_between_banks(
                from_id, to_id, amount, transfer_date,
                description=description, reference=reference, conn=conn
            )
            return journal_id, None
        except Exception as e:
            return None, str(e)

    # ── cash → cash ──
    if from_kind == 'cash' and to_kind == 'cash':
        try:
            from services.cash_service import transfer_between_cashes
            # 🔧 v9.1: transfer_between_cashes تُعيد الآن (journal_id, error)
            journal_id, err = transfer_between_cashes(
                from_id, to_id, amount, transfer_date,
                description=description, reference=reference,
                conn=conn
            )
            if err:
                return None, err
            return journal_id, None
        except Exception as e:
            return None, str(e)

    # ── bank ↔ cash ──
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN IMMEDIATE")

        if from_kind == 'bank':
            from_acc = get_bank_account_by_id(from_id, conn=conn)
            from_table = 'bank_transactions'
            from_fk = 'bank_account_id'
            from_label = 'bank_name'
        else:
            from services.cash_service import get_cash_account_by_id
            from_acc = get_cash_account_by_id(from_id, conn=conn)
            from_table = 'cash_transactions'
            from_fk = 'cash_account_id'
            from_label = 'name'

        if to_kind == 'bank':
            to_acc = get_bank_account_by_id(to_id, conn=conn)
            to_table = 'bank_transactions'
            to_fk = 'bank_account_id'
            to_label = 'bank_name'
        else:
            from services.cash_service import get_cash_account_by_id
            to_acc = get_cash_account_by_id(to_id, conn=conn)
            to_table = 'cash_transactions'
            to_fk = 'cash_account_id'
            to_label = 'name'

        if not from_acc or not to_acc:
            if own_conn:
                conn.rollback()
            return None, "أحد الحسابات غير موجود"

        if not from_acc.get('is_active', 1) or not to_acc.get('is_active', 1):
            if own_conn:
                conn.rollback()
            return None, "أحد الحسابات غير نشط"

        try:
            from_code = _require_account_code(from_acc, from_kind)
            to_code = _require_account_code(to_acc, to_kind)
        except ValueError as ve:
            if own_conn:
                conn.rollback()
            return None, str(ve)

        # 🔧 v9.1: رفض العملة الفارغة
        try:
            from_curr = _require_currency(from_acc, from_kind)
            to_curr = _require_currency(to_acc, to_kind)
        except ValueError as ve:
            if own_conn:
                conn.rollback()
            return None, str(ve)

        if from_curr != to_curr:
            if own_conn:
                conn.rollback()
            return None, (
                f"لا يمكن تحويل الأموال بين حسابين بعملتين مختلفتين حاليًا. "
                f"المصدر: {from_curr} — الوجهة: {to_curr}."
            )

        if from_kind == 'bank':
            ok, err = check_bank_sufficient_balance(from_id, amount, conn=conn)
        else:
            from services.cash_service import check_sufficient_balance
            ok, err = check_sufficient_balance(
                from_code, amount, conn=conn, strict=True
            )
        if not ok:
            if own_conn:
                conn.rollback()
            return None, err

        if not reference:
            reference = _generate_transfer_reference(conn)

        if _reference_exists(conn, reference):
            if own_conn:
                conn.rollback()
            return None, (
                f"مرجع التحويل '{reference}' مستخدم مسبقًا. "
                f"لا يمكن تنفيذ التحويل مرتين."
            )

        lines = [
            {
                "account": to_code,
                "debit": amount,
                "credit": 0.0,
                "currency_code": to_curr,
                "exchange_rate": 1.0
            },
            {
                "account": from_code,
                "debit": 0.0,
                "credit": amount,
                "currency_code": from_curr,
                "exchange_rate": 1.0
            }
        ]

        journal_id, jerr = save_journal_entry(
            entry_date=transfer_date,
            description=description or "تحويل",
            lines=lines,
            conn=conn,
            skip_period_check=False
        )
        if jerr:
            if own_conn:
                conn.rollback()
            return None, f"فشل القيد: {jerr}"

        # نوع الحركة حسب الجدول
        if from_kind == 'bank':
            from_type = 'transfer_out'
        else:
            from_type = 'withdrawal'

        if to_kind == 'bank':
            to_type = 'transfer_in'
        else:
            to_type = 'deposit'

        from_name = from_acc.get(from_label, '')
        to_name = to_acc.get(to_label, '')

        conn.execute(f"""
            INSERT INTO {from_table}
            ({from_fk}, transaction_date, description, type, amount, reference, journal_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            from_id, transfer_date,
            f"تحويل إلى {to_name}",
            from_type, amount, reference, journal_id
        ))

        conn.execute(f"""
            INSERT INTO {to_table}
            ({to_fk}, transaction_date, description, type, amount, reference, journal_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            to_id, transfer_date,
            f"تحويل من {from_name}",
            to_type, amount, reference, journal_id
        ))

        if from_kind == 'bank':
            update_bank_balance(from_id, conn=conn)
        else:
            from services.cash_service import update_cash_balance
            update_cash_balance(from_id, conn=conn)

        if to_kind == 'bank':
            update_bank_balance(to_id, conn=conn)
        else:
            from services.cash_service import update_cash_balance
            update_cash_balance(to_id, conn=conn)

        if own_conn:
            conn.commit()

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


# ===================== استعلامات =====================

def get_bank_transactions(bank_account_id=None, limit=50, conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        if bank_account_id:
            rows = conn.execute(
                """SELECT bt.*, ba.bank_name, ba.account_number
                   FROM bank_transactions bt
                   JOIN bank_accounts ba ON bt.bank_account_id = ba.id
                   WHERE bt.bank_account_id = ?
                   ORDER BY bt.transaction_date DESC, bt.id DESC
                   LIMIT ?""",
                (bank_account_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT bt.*, ba.bank_name, ba.account_number
                   FROM bank_transactions bt
                   JOIN bank_accounts ba ON bt.bank_account_id = ba.id
                   ORDER BY bt.transaction_date DESC, bt.id DESC
                   LIMIT ?""",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            close_connection(conn)


def reconcile_transaction(transaction_id, journal_line_id=None, conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        if own_conn:
            conn.execute("BEGIN IMMEDIATE")
        if journal_line_id:
            conn.execute(
                "UPDATE bank_transactions SET reconciled = 1, journal_line_id = ? WHERE id = ?",
                (journal_line_id, transaction_id)
            )
        else:
            conn.execute(
                "UPDATE bank_transactions SET reconciled = 1 WHERE id = ?",
                (transaction_id,)
            )
        if own_conn:
            conn.commit()
        return True
    except Exception as e:
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise e
    finally:
        if own_conn:
            close_connection(conn)


def get_unreconciled_transactions(bank_account_id, conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        rows = conn.execute(
            """SELECT * FROM bank_transactions
               WHERE bank_account_id = ? AND reconciled = 0
               ORDER BY transaction_date""",
            (bank_account_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            close_connection(conn)


# ===================== المصالحة البنكية =====================

def create_bank_reconciliation(bank_account_id, reconciliation_date,
                                statement_balance, notes="", conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        if own_conn:
            conn.execute("BEGIN IMMEDIATE")

        account = get_bank_account_by_id(bank_account_id, conn=conn)
        if not account:
            raise ValueError("الحساب البنكي غير موجود")

        book_balance = account['current_balance']
        difference = statement_balance - book_balance

        conn.execute(
            """INSERT INTO bank_reconciliations 
               (bank_account_id, reconciliation_date, statement_balance, 
                book_balance, difference, status, notes)
               VALUES (?, ?, ?, ?, ?, 'completed', ?)""",
            (bank_account_id, reconciliation_date, statement_balance,
             book_balance, difference, notes or "")
        )
        if own_conn:
            conn.commit()
        return True, difference
    except Exception as e:
        if own_conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise e
    finally:
        if own_conn:
            close_connection(conn)


def get_reconciliation_history(bank_account_id=None, conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        if bank_account_id:
            rows = conn.execute(
                """SELECT br.*, ba.bank_name, ba.account_number
                   FROM bank_reconciliations br
                   JOIN bank_accounts ba ON br.bank_account_id = ba.id
                   WHERE br.bank_account_id = ?
                   ORDER BY br.reconciliation_date DESC""",
                (bank_account_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT br.*, ba.bank_name, ba.account_number
                   FROM bank_reconciliations br
                   JOIN bank_accounts ba ON br.bank_account_id = ba.id
                   ORDER BY br.reconciliation_date DESC"""
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            close_connection(conn)


# ===================== ملخصات =====================

def get_bank_balance_summary(conn=None):
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        accounts = get_all_bank_accounts(active_only=True, conn=conn)
        summary = []
        total_balance_base = 0.0
        base_currency = get_base_currency()
        base_code = base_currency['code'] if base_currency else 'YER'

        for acc in accounts:
            balance = acc['current_balance']
            currency = acc['currency_code']
            if currency != base_code:
                try:
                    balance_base = convert_amount(balance, currency, base_code)
                except Exception:
                    balance_base = balance
            else:
                balance_base = balance

            summary.append({
                'id': acc['id'],
                'bank_name': acc['bank_name'],
                'account_number': acc['account_number'],
                'currency': currency,
                'balance': balance,
                'balance_base': balance_base
            })
            total_balance_base += balance_base

        return summary, total_balance_base
    finally:
        if own_conn:
            close_connection(conn)
