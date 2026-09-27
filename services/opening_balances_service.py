# services/opening_balances_service.py – الأرصدة الافتتاحية (v2.0)
# ✅ Registry + conn=None + إصلاح bug في حفظ الأرصدة
import sqlite3
from datetime import date
from database import get_connection, close_connection
from services.audit_service import log_action
from services.fifo_service import add_batch
from services.chart_service import get_functional_account
from services.accounting_service import save_journal_entry


def create_opening_tables(conn=None):
    """إنشاء جداول الأرصدة الافتتاحية إذا لم تكن موجودة"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS opening_balances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL,
                account_id INTEGER NOT NULL,
                account_code TEXT NOT NULL,
                account_name TEXT,
                debit REAL DEFAULT 0.0,
                credit REAL DEFAULT 0.0,
                journal_entry_id INTEGER,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS opening_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                quantity REAL NOT NULL,
                unit_cost REAL NOT NULL,
                journal_entry_id INTEGER,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            close_connection(conn)


def get_accounts_for_opening(conn=None):
    """جلب الحسابات المناسبة للأرصدة الافتتاحية"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        accounts = conn.execute("""
            SELECT id, code, name, account_type as type, level
            FROM accounts
            WHERE account_type IN ('Asset', 'Liability', 'Equity')
              AND level >= 2
            ORDER BY code
        """).fetchall()
        return [dict(a) for a in accounts]
    finally:
        if own_conn:
            close_connection(conn)


def get_products_for_opening(conn=None):
    """جلب المنتجات"""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    try:
        products = conn.execute("""
            SELECT id, name, quantity, purchase_price
            FROM products
            ORDER BY name
        """).fetchall()
        return [dict(p) for p in products]
    finally:
        if own_conn:
            close_connection(conn)


def _resolve_account_id(conn, account_identifier):
    """
    تحويل معرف الحساب إلى ID الرقمي.
    يدعم: int، كود، اسم.
    """
    if not account_identifier:
        return None

    if isinstance(account_identifier, int):
        return account_identifier

    identifier = str(account_identifier).strip()

    # ID مباشر
    row = conn.execute(
        "SELECT id FROM accounts WHERE id = ?", (identifier,)
    ).fetchone()
    if row:
        return row["id"]

    # كود
    row = conn.execute(
        "SELECT id FROM accounts WHERE code = ?", (identifier,)
    ).fetchone()
    if row:
        return row["id"]

    # اسم بالضبط
    row = conn.execute(
        "SELECT id FROM accounts WHERE name = ?", (identifier,)
    ).fetchone()
    if row:
        return row["id"]

    # اسم جزئي
    row = conn.execute(
        "SELECT id FROM accounts WHERE name LIKE ?", (f"%{identifier}%",)
    ).fetchone()
    if row:
        return row["id"]

    return None


def create_opening_balances(account_balances, inventory_items, entry_date,
                             created_by="admin", conn=None):
    """
    إنشاء الأرصدة الافتتاحية.
    
    account_balances: [{'account_id':..., 'code':..., 'name':..., 'debit':..., 'credit':...}, ...]
    inventory_items:  [{'product_id':..., 'quantity':..., 'unit_cost':...}, ...]
    
    ⚠️ لا يمسّ الصندوق/البنك — لا يحتاج فحص رصيد.
    
    Returns:
        (entry_id, None) أو (None, "رسالة")
    """
    create_opening_tables(conn=conn)

    inventory_acc_id = get_functional_account("inventory")
    opening_diff_acc_id = get_functional_account("retained_earnings")

    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True

    try:
        # فحص وجود أرصدة سابقة
        existing = conn.execute(
            "SELECT COUNT(*) as cnt FROM opening_balances"
        ).fetchone()
        if existing and existing["cnt"] > 0:
            return None, "الأرصدة الافتتاحية سبق تسجيلها. لا يمكن تكرار العملية."

        if own_conn:
            conn.execute("BEGIN")

        # 1. معالجة المخزون الافتتاحي
        total_inventory_cost = 0.0
        for item in inventory_items:
            qty = float(item.get('quantity', 0))
            cost = float(item.get('unit_cost', 0))
            if qty <= 0:
                continue

            conn.execute(
                "UPDATE products SET quantity = quantity + ? WHERE id = ?",
                (qty, item['product_id'])
            )
            add_batch(
                item['product_id'], qty, cost,
                entry_date, reference="رصيد افتتاحي", conn=conn
            )
            total_inventory_cost += qty * cost

            conn.execute("""
                INSERT INTO opening_inventory 
                    (entry_date, product_id, quantity, unit_cost, created_by) 
                VALUES (?, ?, ?, ?, ?)
            """, (entry_date, item['product_id'], qty, cost, created_by))

        # 2. بناء سطور القيد
        lines = []
        total_debit = 0.0
        total_credit = 0.0

        for bal in account_balances:
            debit_val = round(float(bal.get('debit', 0.0)), 2)
            credit_val = round(float(bal.get('credit', 0.0)), 2)

            if debit_val == 0 and credit_val == 0:
                continue

            identifier = (
                bal.get('account_id')
                or bal.get('code')
                or bal.get('account_code')
            )
            acc_id = _resolve_account_id(conn, identifier)

            if not acc_id:
                raise Exception(
                    f"لم يتم العثور على حساب بالمعرف: {identifier}. "
                    f"تأكد من إضافة الحساب في شجرة الحسابات."
                )

            lines.append({
                "account_id": acc_id,
                "debit": debit_val,
                "credit": credit_val,
                "currency_code": "YER",
                "exchange_rate": 1.0,
            })
            total_debit += debit_val
            total_credit += credit_val

        # 3. إضافة المخزون (مدين)
        if total_inventory_cost > 0:
            if not inventory_acc_id:
                raise Exception(
                    "حساب المخزون الوظيفي (inventory) غير معرف"
                )

            lines.append({
                "account_id": inventory_acc_id,
                "debit": round(total_inventory_cost, 2),
                "credit": 0.0,
                "currency_code": "YER",
                "exchange_rate": 1.0,
            })
            total_debit += round(total_inventory_cost, 2)

        # 4. موازنة القيد عبر الأرباح المبقاة
        diff = round(total_debit - total_credit, 2)
        if abs(diff) > 0.01:
            if not opening_diff_acc_id:
                raise Exception(
                    "حساب الأرباح المبقاة (retained_earnings) غير معرف"
                )

            if diff > 0:
                lines.append({
                    "account_id": opening_diff_acc_id,
                    "debit": 0.0,
                    "credit": diff,
                    "currency_code": "YER",
                    "exchange_rate": 1.0,
                })
            else:
                lines.append({
                    "account_id": opening_diff_acc_id,
                    "debit": abs(diff),
                    "credit": 0.0,
                    "currency_code": "YER",
                    "exchange_rate": 1.0,
                })

        # 5. إنشاء القيد
        entry_id, error = save_journal_entry(
            description=f"قيد الأرصدة الافتتاحية - {entry_date}",
            lines=lines,
            entry_date=entry_date,
            conn=conn,
        )
        if error:
            raise Exception(f"فشل إنشاء القيد المحاسبي: {error}")

        # ============================================================
        # ✅ إصلاح Bug: حفظ كل رصيد بـ acc_id الصحيح (كان يحفظ آخر acc_id فقط)
        # ============================================================
        for bal in account_balances:
            debit_val = round(float(bal.get('debit', 0.0)), 2)
            credit_val = round(float(bal.get('credit', 0.0)), 2)
            if debit_val == 0 and credit_val == 0:
                continue

            identifier = (
                bal.get('account_id')
                or bal.get('code')
                or bal.get('account_code')
            )
            bal_acc_id = _resolve_account_id(conn, identifier)  # ← حل لكل سطر
            if not bal_acc_id:
                continue

            account_code = (
                bal.get('code')
                or bal.get('account_code')
                or str(bal_acc_id)
            )
            account_name = bal.get('name', '')

            conn.execute("""
                INSERT INTO opening_balances 
                    (entry_date, account_id, account_code, account_name,
                     debit, credit, journal_entry_id, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (entry_date, bal_acc_id, account_code, account_name,
                  debit_val, credit_val, entry_id, created_by))

        # تحديث opening_inventory برقم القيد
        conn.execute(
            "UPDATE opening_inventory SET journal_entry_id=? "
            "WHERE entry_date=? AND journal_entry_id IS NULL",
            (entry_id, entry_date)
        )

        if own_conn:
            conn.commit()

        log_action(
            username=created_by,
            action="تسجيل الأرصدة الافتتاحية",
            table_name="opening_balances",
            record_id=entry_id,
            new_value=f"رقم القيد الافتتاحي: {entry_id}"
        )

        return entry_id, None

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
