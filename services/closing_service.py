# services/closing_service.py – منطق قيد إغلاق الحسابات (v2.0)
# ✅ conn=None + Registry + إصلاح N+1 Query + Deadlock
# ✅ تسجيل closing_logs + get_functional_account + username
from datetime import date
from database import get_connection, close_connection
from services import cost_center_service as ccs
from services.audit_service import log_action
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


def _validate_year(year) -> tuple[bool, str]:
    """تحقق أن السنة صالحة"""
    try:
        y = int(year)
        if y < 1900 or y > 2200:
            return False, f"السنة {y} خارج النطاق المعقول"
        return True, str(y)
    except (TypeError, ValueError):
        return False, f"السنة غير صالحة: {year}"


# ============================================================
# الجداول
# ============================================================
def create_closing_table(conn=None):
    """إنشاء جدول closing_logs إذا لم يكن موجوداً"""
    c, owns = _resolve_conn(conn)
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS closing_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year TEXT NOT NULL,
                cost_center_id INTEGER,
                entry_id INTEGER NOT NULL,
                net_income REAL NOT NULL,
                closed_at TEXT NOT NULL,
                closed_by TEXT NOT NULL,
                UNIQUE(year, cost_center_id)
            )
        """)
        if owns:
            c.commit()
    finally:
        _release_conn(c, owns)


def ensure_closing_table():
    """ضمان وجود الجدول عند بدء التطبيق"""
    create_closing_table()


def _is_year_closed(year, cost_center_id=None, conn=None) -> bool:
    """فحص: هل السنة (أو مركز التكلفة) مُغلقة مسبقاً؟"""
    c, owns = _resolve_conn(conn)
    try:
        if cost_center_id is None:
            row = c.execute(
                "SELECT id FROM closing_logs WHERE year = ? AND cost_center_id IS NULL",
                (str(year),)
            ).fetchone()
        else:
            row = c.execute(
                "SELECT id FROM closing_logs WHERE year = ? AND cost_center_id = ?",
                (str(year), cost_center_id)
            ).fetchone()
        return row is not None
    finally:
        _release_conn(c, owns)


def _log_closing(year, cost_center_id, entry_id, net_income, username, conn):
    """تسجيل الإغلاق في closing_logs (باستخدام نفس الاتصال)"""
    conn.execute("""
        INSERT INTO closing_logs
            (year, cost_center_id, entry_id, net_income, closed_at, closed_by)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        str(year),
        cost_center_id,
        entry_id,
        float(net_income),
        date.today().strftime("%Y-%m-%d %H:%M:%S"),
        username
    ))


# ============================================================
# قراءة الأرصدة — ✅ كل شيء بنفس الاتصال
# ============================================================
def get_account_balance(account_code, conn=None):
    """
    جلب رصيد حساب محدد.
    ✅ يقبل conn=None لتجنب N+1 داخل Transaction.
    """
    c, owns = _resolve_conn(conn)
    try:
        row = c.execute("""
            SELECT COALESCE(SUM(debit), 0) - COALESCE(SUM(credit), 0) AS balance
            FROM journal_lines
            WHERE account_name = ?
        """, (account_code,)).fetchone()
        return float(row["balance"]) if row else 0.0
    finally:
        _release_conn(c, owns)


def get_all_accounts_by_prefix(prefix, conn=None):
    """جلب الحسابات حسب البادئة (dict list)"""
    c, owns = _resolve_conn(conn)
    try:
        rows = c.execute(
            "SELECT code, name, is_debit FROM accounts WHERE code LIKE ? ORDER BY code",
            (prefix + "%",)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        _release_conn(c, owns)


def _get_balances_for_prefix(prefix, conn):
    """
    ✅ حساب أرصدة كل حسابات بادئة معينة باستعلام واحد (بدل N+1).
    يُرجع {code: balance}
    """
    rows = conn.execute("""
        SELECT jl.account_name AS code,
               COALESCE(SUM(jl.debit), 0) - COALESCE(SUM(jl.credit), 0) AS balance
        FROM journal_lines jl
        WHERE jl.account_name LIKE ?
        GROUP BY jl.account_name
    """, (prefix + "%",)).fetchall()
    return {r["code"]: float(r["balance"] or 0) for r in rows}


# ============================================================
# إغلاق السنة المالية (عام)
# ============================================================
def create_closing_entry(year, retained_earnings_code=None,
                          username="admin", conn=None):
    """
    إنشاء قيد إغلاق السنة المالية العامة (للشركة).
    تُرجع (success, net_income, error_message)
    ✅ يستخدم استعلام واحد للأرصدة (لا N+1).
    ✅ يسجّل في closing_logs.
    """
    ok, year_str = _validate_year(year)
    if not ok:
        return False, 0, year_str
    year = year_str

    # ✅ الأرباح المحتجزة من الحسابات الوظيفية إن لم تُمرَّر
    if not retained_earnings_code:
        retained_earnings_code = get_functional_account("retained_earnings") or "32"

    c, owns = _resolve_conn(conn)
    try:
        c.execute("BEGIN IMMEDIATE")

        # ✅ فحص الإغلاق المسبق من closing_logs
        if _is_year_closed(year, cost_center_id=None, conn=c):
            c.rollback()
            return False, 0, f"السنة {year} مُغلقة مسبقاً"

        # فحص احتياطي: قيد بنفس الوصف
        desc = f"قيد إغلاق السنة المالية {year}"
        existing = c.execute(
            "SELECT id FROM journal_entries WHERE description = ?",
            (desc,)
        ).fetchone()
        if existing:
            c.rollback()
            return False, 0, f"يوجد بالفعل قيد إغلاق للسنة {year}"

        # ✅ أرصدة الإيرادات — استعلام واحد
        revenue_balances = _get_balances_for_prefix("4", c)
        revenue_accounts = get_all_accounts_by_prefix("4", conn=c)

        total_revenue = 0.0
        revenue_details = []
        for acc in revenue_accounts:
            balance = revenue_balances.get(acc["code"], 0.0)
            # طبيعة الإيراد دائنة: الرصيد سالب عادة
            amount = -balance if acc["is_debit"] == "credit" else balance
            if abs(amount) > 0.001:
                total_revenue += amount
                revenue_details.append((acc["code"], acc["name"], amount))

        # ✅ أرصدة المصروفات — استعلام واحد
        expense_balances = _get_balances_for_prefix("5", c)
        expense_accounts = get_all_accounts_by_prefix("5", conn=c)

        total_expense = 0.0
        expense_details = []
        for acc in expense_accounts:
            balance = expense_balances.get(acc["code"], 0.0)
            amount = balance if acc["is_debit"] == "debit" else -balance
            if abs(amount) > 0.001:
                total_expense += amount
                expense_details.append((acc["code"], acc["name"], amount))

        net_income = total_revenue - total_expense

        # إنشاء قيد اليومية
        date_str = f"{year}-12-31"
        cur = c.execute(
            "INSERT INTO journal_entries (date, description, reference) VALUES (?, ?, ?)",
            (date_str, desc, f"إغلاق {year}")
        )
        entry_id = cur.lastrowid

        # إقفال الإيرادات (مدين)
        for code, name, amt in revenue_details:
            c.execute("""
                INSERT INTO journal_lines
                (entry_id, account_name, debit, credit, currency_code, exchange_rate)
                VALUES (?, ?, ?, 0, 'YER', 1.0)
            """, (entry_id, code, abs(amt)))

        # إقفال المصروفات (دائن)
        for code, name, amt in expense_details:
            c.execute("""
                INSERT INTO journal_lines
                (entry_id, account_name, debit, credit, currency_code, exchange_rate)
                VALUES (?, ?, 0, ?, 'YER', 1.0)
            """, (entry_id, code, abs(amt)))

        # توجيه صافي الدخل إلى الأرباح المحتجزة
        if net_income > 0:
            c.execute("""
                INSERT INTO journal_lines
                (entry_id, account_name, debit, credit, currency_code, exchange_rate)
                VALUES (?, ?, 0, ?, 'YER', 1.0)
            """, (entry_id, retained_earnings_code, net_income))
        elif net_income < 0:
            c.execute("""
                INSERT INTO journal_lines
                (entry_id, account_name, debit, credit, currency_code, exchange_rate)
                VALUES (?, ?, ?, 0, 'YER', 1.0)
            """, (entry_id, retained_earnings_code, -net_income))

        # ✅ تسجيل في closing_logs
        _log_closing(year, None, entry_id, net_income, username, c)

        if owns:
            c.commit()

        log_action(
            username=username,
            action="إغلاق سنة مالية",
            table_name="journal_entries",
            record_id=entry_id,
            new_value=f"إغلاق السنة المالية {year}, صافي الدخل: {net_income:,.2f}"
        )

        return True, net_income, None

    except Exception as e:
        if owns:
            try: c.rollback()
            except Exception: pass
        return False, 0, str(e)
    finally:
        _release_conn(c, owns)


# ============================================================
# إغلاق مركز تكلفة
# ============================================================
def create_cost_center_closing_entry(year, cost_center_id,
                                       retained_earnings_code=None,
                                       username="admin", conn=None):
    """
    إنشاء قيد إغلاق لمركز تكلفة محدد.
    تُرجع (success, net_income, error_message)
    """
    ok, year_str = _validate_year(year)
    if not ok:
        return False, 0, year_str
    year = year_str

    if not retained_earnings_code:
        retained_earnings_code = get_functional_account("retained_earnings") or "32"

    # التحقق من وجود المركز (خارج Transaction للقراءة فقط)
    center = ccs.get_cost_center_by_id(cost_center_id)
    if not center:
        return False, 0, "مركز التكلفة غير موجود"

    c, owns = _resolve_conn(conn)
    try:
        c.execute("BEGIN IMMEDIATE")

        # ✅ فحص الإغلاق المسبق
        if _is_year_closed(year, cost_center_id=cost_center_id, conn=c):
            c.rollback()
            return False, 0, (
                f"مركز التكلفة {center['code']} مُغلق مسبقاً للسنة {year}"
            )

        desc = f"قيد إغلاق مركز تكلفة {center['code']} - {center['name']} للسنة {year}"
        existing = c.execute(
            "SELECT id FROM journal_entries WHERE description = ?",
            (desc,)
        ).fetchone()
        if existing:
            c.rollback()
            return False, 0, f"يوجد بالفعل قيد إغلاق للمركز {center['code']} للسنة {year}"

        # قائمة الدخل المخصصة للمركز
        income_stmt = ccs.get_cost_center_income_statement(
            cost_center_id, f"{year}-01-01", f"{year}-12-31"
        )
        net_income = float(income_stmt['net_profit'])
        details = income_stmt['details']

        date_str = f"{year}-12-31"
        cur = c.execute(
            "INSERT INTO journal_entries (date, description, reference) VALUES (?, ?, ?)",
            (date_str, desc, f"إغلاق مركز {center['code']} - {year}")
        )
        entry_id = cur.lastrowid

        # أسطر الإغلاق
        for item in details:
            if abs(float(item['net'])) < 0.001:
                continue
            account_code = item['account_code']
            account_type = item['account_type']
            abs_net = abs(float(item['net']))

            if account_type in ('revenue', 'income'):
                cur_line = c.execute("""
                    INSERT INTO journal_lines
                    (entry_id, account_name, debit, credit, currency_code, exchange_rate)
                    VALUES (?, ?, ?, 0, 'YER', 1.0)
                """, (entry_id, account_code, abs_net))
            elif account_type in ('expense', 'cost_of_sales'):
                cur_line = c.execute("""
                    INSERT INTO journal_lines
                    (entry_id, account_name, debit, credit, currency_code, exchange_rate)
                    VALUES (?, ?, 0, ?, 'YER', 1.0)
                """, (entry_id, account_code, abs_net))
            else:
                if item['net'] > 0:
                    cur_line = c.execute("""
                        INSERT INTO journal_lines
                        (entry_id, account_name, debit, credit, currency_code, exchange_rate)
                        VALUES (?, ?, ?, 0, 'YER', 1.0)
                    """, (entry_id, account_code, abs_net))
                else:
                    cur_line = c.execute("""
                        INSERT INTO journal_lines
                        (entry_id, account_name, debit, credit, currency_code, exchange_rate)
                        VALUES (?, ?, 0, ?, 'YER', 1.0)
                    """, (entry_id, account_code, abs_net))

            line_id = cur_line.lastrowid
            ccs.allocate_journal_line(line_id, [{
                'cost_center_id': cost_center_id,
                'amount': abs_net,
                'percentage': 100.0
            }])

        # سطر صافي الدخل
        if net_income > 0:
            cur_line = c.execute("""
                INSERT INTO journal_lines
                (entry_id, account_name, debit, credit, currency_code, exchange_rate)
                VALUES (?, ?, 0, ?, 'YER', 1.0)
            """, (entry_id, retained_earnings_code, net_income))
        elif net_income < 0:
            cur_line = c.execute("""
                INSERT INTO journal_lines
                (entry_id, account_name, debit, credit, currency_code, exchange_rate)
                VALUES (?, ?, ?, 0, 'YER', 1.0)
            """, (entry_id, retained_earnings_code, -net_income))

        if abs(net_income) > 0.001:
            line_id = cur_line.lastrowid
            ccs.allocate_journal_line(line_id, [{
                'cost_center_id': cost_center_id,
                'amount': abs(net_income),
                'percentage': 100.0
            }])

        # ✅ تسجيل في closing_logs
        _log_closing(year, cost_center_id, entry_id, net_income, username, c)

        if owns:
            c.commit()

        log_action(
            username=username,
            action="إغلاق سنة مالية (مركز تكلفة)",
            table_name="journal_entries",
            record_id=entry_id,
            new_value=(
                f"إغلاق مركز {center['code']} - {center['name']} "
                f"للسنة {year}, صافي الدخل: {net_income:,.2f}"
            )
        )

        return True, net_income, None

    except Exception as e:
        if owns:
            try: c.rollback()
            except Exception: pass
        return False, 0, str(e)
    finally:
        _release_conn(c, owns)


# ============================================================
# تقرير: أرصدة الإغلاق
# ============================================================
def get_closing_summary(year, conn=None):
    """
    ملخص الإغلاق لسنة معينة.
    ✅ يعرض أرصدة الصناديق والبنوك (لم تُغلق لكن مفيدة للسياق).
    """
    ok, year_str = _validate_year(year)
    if not ok:
        return {"error": year_str}

    c, owns = _resolve_conn(conn)
    try:
        result = {"year": year_str}

        # حالة الإغلاق
        row = c.execute(
            "SELECT entry_id, net_income, closed_at, closed_by "
            "FROM closing_logs WHERE year = ? AND cost_center_id IS NULL",
            (year_str,)
        ).fetchone()
        if row:
            result["closed"] = True
            result["entry_id"] = row["entry_id"]
            result["net_income"] = float(row["net_income"] or 0)
            result["closed_at"] = row["closed_at"]
            result["closed_by"] = row["closed_by"]
        else:
            result["closed"] = False

        # أرصدة الصندوق
        try:
            rows = c.execute("""
                SELECT name, currency_code, current_balance
                FROM cash_accounts WHERE is_active = 1 ORDER BY name
            """).fetchall()
            result["cash_accounts"] = [dict(r) for r in rows]
            result["cash_total"] = sum(
                float(r["current_balance"] or 0) for r in rows
            )
        except Exception:
            result["cash_accounts"] = []
            result["cash_total"] = 0.0

        # أرصدة البنك
        try:
            rows = c.execute("""
                SELECT bank_name, account_number, currency_code, current_balance
                FROM bank_accounts WHERE is_active = 1 ORDER BY bank_name
            """).fetchall()
            result["bank_accounts"] = [dict(r) for r in rows]
            result["bank_total"] = sum(
                float(r["current_balance"] or 0) for r in rows
            )
        except Exception:
            result["bank_accounts"] = []
            result["bank_total"] = 0.0

        result["liquidity_total"] = result["cash_total"] + result["bank_total"]
        return result
    finally:
        _release_conn(c, owns)
