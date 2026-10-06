# services/cash_service.py – وحدة الصندوق متعدد العملات (v8.0)
# ✅ متوافق مع Connection Registry
# ✅ حماية صارمة من الرصيد السالب
# ✅ v7.0: توليد كود فريد لكل صندوق + إنشاء حساب نظامي
# ✅ v8.0: إضافة transfer_funds (توافق) — تدعم 4 حالات تحويل
import sqlite3
from datetime import date
from database import get_connection, close_connection
from services.audit_service import log_action
from services.currency_service import get_base_currency, get_exchange_rate, convert_amount
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry


# ============================================================
# ✅ مساعد: قراءة الحساب الوظيفي من نفس الاتصال
# ============================================================
def _read_functional_code(conn, functional_type):
    """قراءة كود الحساب الوظيفي من نفس الاتصال"""
    try:
        r = conn.execute(
            "SELECT code FROM accounts WHERE functional_type = ? AND is_active = 1 LIMIT 1",
            (functional_type,)
        ).fetchone()
        if r:
            return r["code"]
    except Exception:
        pass
    return get_functional_account(functional_type)


# ============================================================
# ✅ v7.0: دالة مساعدة — توليد كود فريد للصندوق
# ============================================================
def _generate_unique_cash_code(conn):
    """
    توليد كود فريد للصندوق بالشكل:
        1101.01, 1101.02, 1101.03, ...
    """
    parent = conn.execute("""
        SELECT id, code, level FROM accounts
        WHERE functional_type = 'cash' AND is_active = 1
        ORDER BY LENGTH(code), code
        LIMIT 1
    """).fetchone()

    if not parent:
        raise ValueError(
            "حساب الصندوق الأب مفقود في شجرة الحسابات. "
            "أضف حساباً بالنوع الوظيفي 'cash' أولاً."
        )

    parent_code = parent["code"]
    parent_id = parent["id"]
    parent_level = parent["level"]

    count = conn.execute(
        "SELECT COUNT(*) FROM cash_accounts"
    ).fetchone()[0]

    new_code = f"{parent_code}.{(count + 1):02d}"

    return {
        "parent_id": parent_id,
        "parent_code": parent_code,
        "parent_level": parent_level,
        "new_code": new_code,
    }


# ============================================================
# ✅ v7.0: دالة مساعدة — إنشاء الحساب النظامي
# ============================================================
def _create_system_account(conn, code, name, parent_id, parent_level,
                            functional_type='cash'):
    """
    إنشاء حساب نظامي في شجرة الحسابات.
    - is_system = 1 → مخفي افتراضياً من الواجهة
    """
    conn.execute("""
        INSERT INTO accounts
        (code, name, parent_id, level, is_debit, is_active,
         account_type, functional_type, is_system)
        VALUES (?, ?, ?, ?, 'debit', 1, 'Asset', ?, 1)
    """, (code, name, parent_id, parent_level + 1, functional_type))


# ============================================================
# ✅ دالة فحص كفاية الرصيد (للصندوق والبنك) — نسخة صارمة
# ============================================================
def check_sufficient_balance(account_code, amount, conn=None, strict=True):
    """
    فحص كفاية الرصيد قبل الصرف.
    """
    if account_code is None:
        return False, "كود الحساب مفقود"

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
        # 1) البحث في الصناديق النقدية
        row = conn.execute(
            "SELECT name, current_balance FROM cash_accounts "
            "WHERE account_code = ? AND is_active = 1",
            (account_code,)
        ).fetchone()

        if row:
            current = float(row['current_balance'] or 0)
            if current < -0.001:
                return False, (
                    f"⚠️ رصيد الصندوق '{row['name']}' سالب ({current:,.2f}) "
                    f"— راجع الحركات السابقة"
                )
            if amount_float > current + 0.001:
                return False, (
                    f"❌ الرصيد غير كافٍ في الصندوق '{row['name']}'. "
                    f"المتاح: {current:,.2f} — المطلوب: {amount_float:,.2f}"
                )
            return True, None

        # 2) البحث في الحسابات البنكية
        try:
            row = conn.execute(
                "SELECT bank_name, current_balance FROM bank_accounts "
                "WHERE account_code = ? AND is_active = 1",
                (account_code,)
            ).fetchone()

            if row:
                current = float(row['current_balance'] or 0)
                if current < -0.001:
                    return False, (
                        f"⚠️ رصيد البنك '{row['bank_name']}' سالب ({current:,.2f}) "
                        f"— راجع الحركات السابقة"
                    )
                if amount_float > current + 0.001:
                    return False, (
                        f"❌ الرصيد غير كافٍ في البنك '{row['bank_name']}'. "
                        f"المتاح: {current:,.2f} — المطلوب: {amount_float:,.2f}"
                    )
                return True, None
        except Exception:
            pass

        # 3) لم نجد الحساب
        if strict:
            return False, (
                f"⚠️ الحساب '{account_code}' غير موجود في الصناديق أو البنوك. "
                f"إذا كانت عملية إدارية، استخدم skip_balance_check=True"
            )
        return True, None

    finally:
        if own_conn:
            close_connection(conn)


# ============================================================
# إنشاء الجداول
# ============================================================
def create_cash_tables():
    """إنشاء جداول الصندوق إذا لم تكن موجودة"""
    conn = get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cash_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                currency_code TEXT NOT NULL DEFAULT 'YER',
                opening_balance REAL DEFAULT 0.0,
                current_balance REAL DEFAULT 0.0,
                account_code TEXT,
                is_active INTEGER DEFAULT 1 CHECK(is_active IN (0,1)),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cash_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cash_account_id INTEGER NOT NULL,
                transaction_date TEXT NOT NULL,
                description TEXT,
                type TEXT NOT NULL CHECK(type IN ('deposit','withdrawal')),
                amount REAL NOT NULL CHECK(amount > 0),
                reference TEXT,
                journal_id INTEGER,
                journal_line_id INTEGER,
                voucher_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cash_account_id) REFERENCES cash_accounts(id)
            )
        """)
        conn.commit()
    finally:
        close_connection(conn)


# ============================================================
# ✅ إنشاء حساب صندوق — مع قيد افتتاحي تلقائي + كود فريد
# ============================================================
def create_cash_account(name, currency_code="YER", opening_balance=0.0,
                         account_code=None, created_by="admin"):
    """إنشاء حساب صندوق جديد."""
    if not name or not str(name).strip():
        return False, "اسم الصندوق مطلوب"

    try:
        opening_balance = float(opening_balance or 0)
    except (TypeError, ValueError):
        return False, "الرصيد الافتتاحي غير صحيح"

    if opening_balance < 0:
        return False, "الرصيد الافتتاحي لا يمكن أن يكون سالباً"

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")

        if account_code:
            final_account_code = account_code
        else:
            code_info = _generate_unique_cash_code(conn)
            final_account_code = code_info["new_code"]

            _create_system_account(
                conn,
                code=final_account_code,
                name=str(name).strip(),
                parent_id=code_info["parent_id"],
                parent_level=code_info["parent_level"],
                functional_type='cash',
            )

        capital_account_code = None
        if opening_balance > 0:
            capital_account_code = _read_functional_code(conn, "capital")
            if not capital_account_code:
                raise ValueError(
                    "حساب رأس المال مفقود في شجرة الحسابات. "
                    "أضف حساباً بالنوع الوظيفي 'capital' أولاً."
                )

        cur = conn.execute(
            """INSERT INTO cash_accounts
               (name, currency_code, opening_balance, current_balance, account_code)
               VALUES (?, ?, ?, ?, ?)""",
            (str(name).strip(), currency_code, opening_balance,
             opening_balance, final_account_code)
        )
        cash_account_id = cur.lastrowid

        entry_id = None
        if opening_balance > 0:
            lines = [
                {
                    "account": final_account_code,
                    "debit": opening_balance,
                    "credit": 0.0,
                    "currency_code": currency_code,
                    "exchange_rate": 1.0,
                },
                {
                    "account": capital_account_code,
                    "debit": 0.0,
                    "credit": opening_balance,
                    "currency_code": currency_code,
                    "exchange_rate": 1.0,
                },
            ]

            _journal_result = save_journal_entry(
                description=f"رصيد افتتاحي لصندوق {name}",
                lines=lines,
                entry_date=date.today().strftime("%Y-%m-%d"),
                conn=conn,
                skip_period_check=True,
            )

            if isinstance(_journal_result, tuple):
                entry_id, jerr = _journal_result
                if jerr:
                    raise ValueError(f"فشل القيد الافتتاحي: {jerr}")

        conn.commit()

        try:
            log_action(
                username=created_by,
                action="إنشاء صندوق",
                table_name="cash_accounts",
                record_id=cash_account_id,
                new_value=(
                    f"صندوق: {name}, العملة: {currency_code}, "
                    f"الرصيد الافتتاحي: {opening_balance:,.2f}, "
                    f"كود الحساب: {final_account_code}"
                )
            )
        except Exception:
            pass

        if opening_balance > 0:
            return True, (
                f"تم إنشاء الصندوق بنجاح مع قيد افتتاحي رقم {entry_id} "
                f"برصيد {opening_balance:,.2f} {currency_code}"
            )
        return True, "تم إنشاء حساب الصندوق بنجاح"

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, str(e)
    finally:
        close_connection(conn)


def get_all_cash_accounts(active_only=True, conn=None):
    """جلب جميع حسابات الصندوق"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        query = "SELECT * FROM cash_accounts"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY name"
        accounts = conn.execute(query).fetchall()
        return [dict(a) for a in accounts]
    finally:
        if own_conn:
            close_connection(conn)


def get_cash_account_by_id(account_id, conn=None):
    """جلب حساب صندوق محدد"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        account = conn.execute(
            "SELECT * FROM cash_accounts WHERE id=?", (account_id,)
        ).fetchone()
        return dict(account) if account else None
    finally:
        if own_conn:
            close_connection(conn)


# ============================================================
# ✅ update_cash_balance — نسخة ذرّية (Atomic)
# ============================================================
def update_cash_balance(account_id, conn=None):
    """تحديث رصيد الصندوق — ذرّي بالكامل."""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN IMMEDIATE")

        conn.execute("""
            UPDATE cash_accounts
            SET current_balance = opening_balance + COALESCE((
                SELECT SUM(
                    CASE WHEN type='deposit' THEN amount ELSE -amount END
                )
                FROM cash_transactions
                WHERE cash_account_id = ?
            ), 0)
            WHERE id = ?
        """, (account_id, account_id))

        row = conn.execute(
            "SELECT current_balance FROM cash_accounts WHERE id = ?",
            (account_id,)
        ).fetchone()
        new_balance = float(row['current_balance'] or 0) if row else 0.0

        if new_balance < -0.01:
            try:
                log_action(
                    username="system",
                    action="⚠️ رصيد صندوق سالب",
                    table_name="cash_accounts",
                    record_id=account_id,
                    new_value=f"الرصيد: {new_balance:,.2f}"
                )
            except Exception:
                pass

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


# ============================================================
# حركات الصندوق
# ============================================================
def add_cash_transaction(
    cash_account_id,
    transaction_date,
    description,
    trans_type,
    amount,
    reference="",
    contra_account_code=None,
    create_journal=True,
    journal_line_id=None,
    voucher_id=None,
    conn=None,
    skip_balance_check=False,
    created_by="admin"
):
    """إضافة حركة صندوق مع قيد محاسبي تلقائي."""
    if trans_type not in ('deposit', 'withdrawal'):
        return False, "نوع الحركة غير صالح"

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return False, "المبلغ غير صحيح"

    if amount <= 0:
        return False, "المبلغ يجب أن يكون أكبر من صفر"

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        if own_conn:
            conn.execute("BEGIN IMMEDIATE")

        account = get_cash_account_by_id(cash_account_id, conn=conn)
        if not account:
            if own_conn:
                conn.rollback()
            return False, "حساب الصندوق غير موجود"

        cash_code = account.get('account_code') or _read_functional_code(conn, "cash")
        currency = account.get('currency_code', 'YER')

        if trans_type == 'withdrawal' and not skip_balance_check:
            ok, err = check_sufficient_balance(
                cash_code, amount, conn=conn, strict=True
            )
            if not ok:
                if own_conn:
                    conn.rollback()
                return False, err

        base_currency = get_base_currency()
        if currency == base_currency['code']:
            exchange_rate = 1.0
        else:
            exchange_rate = get_exchange_rate(currency, base_currency['code']) or 1.0

        journal_id = None

        if create_journal:
            target_contra_code = contra_account_code or _read_functional_code(conn, "bank")
            lines = []

            if trans_type == 'deposit':
                lines.append({
                    "account": cash_code,
                    "debit": amount,
                    "credit": 0.0,
                    "currency_code": currency,
                    "exchange_rate": exchange_rate
                })
                lines.append({
                    "account": target_contra_code,
                    "debit": 0.0,
                    "credit": amount,
                    "currency_code": currency,
                    "exchange_rate": exchange_rate
                })
            else:
                lines.append({
                    "account": target_contra_code,
                    "debit": amount,
                    "credit": 0.0,
                    "currency_code": currency,
                    "exchange_rate": exchange_rate
                })
                lines.append({
                    "account": cash_code,
                    "debit": 0.0,
                    "credit": amount,
                    "currency_code": currency,
                    "exchange_rate": exchange_rate
                })

            _journal_result = save_journal_entry(
                entry_date=transaction_date,
                description=f"{description} ({reference})".strip(),
                lines=lines,
                conn=conn
            )

            if isinstance(_journal_result, tuple):
                journal_id = _journal_result[0]
                jerr = _journal_result[1] if len(_journal_result) > 1 else None
                if jerr:
                    if own_conn:
                        conn.rollback()
                    return False, f"فشل القيد المحاسبي: {jerr}"
            else:
                journal_id = _journal_result

        conn.execute(
            """INSERT INTO cash_transactions
               (cash_account_id, transaction_date, description, type, amount,
                reference, journal_id, journal_line_id, voucher_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cash_account_id, transaction_date, description, trans_type,
             amount, reference, journal_id, journal_line_id, voucher_id)
        )

        new_balance = update_cash_balance(cash_account_id, conn=conn)

        if own_conn:
            conn.commit()

        if new_balance < -0.01:
            try:
                log_action(
                    username=created_by,
                    action="⚠️ حركة تسببت برصيد سالب",
                    table_name="cash_transactions",
                    new_value=(
                        f"صندوق: {account['name']}, المبلغ: {amount:,.2f} "
                        f"{currency}, الرصيد الناتج: {new_balance:,.2f}"
                    )
                )
            except Exception:
                pass

        log_action(
            username=created_by,
            action=f"{'إيداع' if trans_type == 'deposit' else 'سحب'} صندوق",
            table_name="cash_transactions",
            new_value=(
                f"صندوق: {account['name']}, المبلغ: {amount:,.2f} {currency}, "
                f"الرصيد الجديد: {new_balance:,.2f}"
            )
        )

        return True, f"تمت الحركة بنجاح. الرصيد الحالي: {new_balance:,.2f}"

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
# التحويل بين الصناديق
# ============================================================
def transfer_between_cashes(from_account_id, to_account_id, amount, transfer_date,
                             description="تحويل بين الصناديق", reference="",
                             created_by="admin"):
    """تحويل بين صندوقين — مع فحص الرصيد."""
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return False, "المبلغ غير صحيح"

    if amount <= 0:
        return False, "المبلغ يجب أن يكون أكبر من صفر"

    if from_account_id == to_account_id:
        return False, "لا يمكن التحويل لنفس الصندوق"

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")

        from_acc = get_cash_account_by_id(from_account_id, conn=conn)
        to_acc = get_cash_account_by_id(to_account_id, conn=conn)

        if not from_acc or not to_acc:
            conn.rollback()
            return False, "أحد حسابات الصندوق غير موجود"

        from_code = from_acc.get('account_code') or _read_functional_code(conn, "cash")
        to_code = to_acc.get('account_code') or _read_functional_code(conn, "cash")

        ok, err = check_sufficient_balance(
            from_code, amount, conn=conn, strict=True
        )
        if not ok:
            conn.rollback()
            return False, err

        from_curr = from_acc.get('currency_code', 'YER')
        to_curr = to_acc.get('currency_code', 'YER')

        from_rate = get_exchange_rate(from_curr)
        to_rate = get_exchange_rate(to_curr)

        base_amount = amount * from_rate
        converted_to_amount = base_amount / to_rate if to_rate else amount

        lines = [
            {
                "account": to_code,
                "debit": converted_to_amount,
                "credit": 0.0,
                "currency_code": to_curr,
                "exchange_rate": to_rate
            },
            {
                "account": from_code,
                "debit": 0.0,
                "credit": amount,
                "currency_code": from_curr,
                "exchange_rate": from_rate
            }
        ]

        result = save_journal_entry(
            entry_date=transfer_date,
            description=f"{description} من {from_acc['name']} إلى {to_acc['name']}",
            lines=lines,
            conn=conn
        )
        if isinstance(result, tuple):
            journal_id = result[0]
            jerr = result[1] if len(result) > 1 else None
            if jerr:
                conn.rollback()
                return False, f"فشل القيد: {jerr}"
        else:
            journal_id = result

        ok1, msg1 = add_cash_transaction(
            from_account_id, transfer_date,
            f"تحويل إلى {to_acc['name']}",
            'withdrawal', amount, reference,
            create_journal=False,
            conn=conn,
            skip_balance_check=True,
            created_by=created_by
        )
        if not ok1:
            conn.rollback()
            return False, f"فشل الخصم: {msg1}"

        ok2, msg2 = add_cash_transaction(
            to_account_id, transfer_date,
            f"تحويل من {from_acc['name']}",
            'deposit', converted_to_amount, reference,
            create_journal=False,
            conn=conn,
            skip_balance_check=True,
            created_by=created_by
        )
        if not ok2:
            conn.rollback()
            return False, f"فشل الإيداع: {msg2}"

        conn.commit()
        return True, f"تم التحويل بنجاح برقم قيد: {journal_id}"

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, str(e)
    finally:
        close_connection(conn)


# ============================================================
# ✅ v8.0: دالة التحويل الشاملة (توافق — تُعيد توجيه للـ bank_service)
# ============================================================
def transfer_funds(from_kind, from_id, to_kind, to_id, amount,
                   transfer_date, description="تحويل", reference="",
                   conn=None):
    """
    ✅ v8.0: دالة توافق — تُعيد توجيه إلى bank_service.transfer_funds.
    
    السبب: تجنّب التكرار — الدالة الشاملة موجودة في bank_service فقط.
    هذا الملف يُتيح الاستدعاء من كود يعتمد على cash_service.
    """
    from services.bank_service import transfer_funds as bank_transfer_funds
    return bank_transfer_funds(
        from_kind, from_id, to_kind, to_id, amount,
        transfer_date, description=description,
        reference=reference, conn=conn
    )


# ============================================================
# سجل الحركات
# ============================================================
def get_cash_transactions(cash_account_id=None, limit=50, conn=None):
    """جلب حركات الصندوق"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        if cash_account_id:
            rows = conn.execute(
                """SELECT ct.*, ca.name as account_name, ca.currency_code
                   FROM cash_transactions ct
                   JOIN cash_accounts ca ON ct.cash_account_id = ca.id
                   WHERE ct.cash_account_id = ?
                   ORDER BY ct.transaction_date DESC, ct.id DESC LIMIT ?""",
                (cash_account_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT ct.*, ca.name as account_name, ca.currency_code
                   FROM cash_transactions ct
                   JOIN cash_accounts ca ON ct.cash_account_id = ca.id
                   ORDER BY ct.transaction_date DESC, ct.id DESC LIMIT ?""",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        if own_conn:
            close_connection(conn)


# ============================================================
# التقارير
# ============================================================
def get_cash_balance_summary(conn=None):
    """ملخص أرصدة جميع صناديق النقدية"""
    accounts = get_all_cash_accounts(active_only=True, conn=conn)
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
            'name': acc['name'],
            'currency': currency,
            'balance': balance,
            'balance_base': balance_base
        })
        total_balance_base += balance_base

    return summary, total_balance_base


def get_cash_statement(cash_account_id, from_date, to_date, conn=None):
    """كشف حساب الصندوق لفترة محددة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        account = get_cash_account_by_id(cash_account_id, conn=conn)
        if not account:
            return None, "الحساب غير موجود"

        balance_before = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN type='deposit' THEN amount ELSE -amount END), 0) "
            "FROM cash_transactions WHERE cash_account_id=? AND transaction_date < ?",
            (cash_account_id, from_date)
        ).fetchone()[0]
        opening = account['opening_balance'] + balance_before

        transactions = conn.execute(
            "SELECT * FROM cash_transactions "
            "WHERE cash_account_id=? AND transaction_date BETWEEN ? AND ? "
            "ORDER BY transaction_date, id",
            (cash_account_id, from_date, to_date)
        ).fetchall()

        period_movement = sum(
            t['amount'] if t['type'] == 'deposit' else -t['amount']
            for t in transactions
        )
        closing = opening + period_movement

        return {
            'account': account,
            'from_date': from_date,
            'to_date': to_date,
            'opening_balance': opening,
            'transactions': [dict(t) for t in transactions],
            'closing_balance': closing
        }, None
    finally:
        if own_conn:
            close_connection(conn)
