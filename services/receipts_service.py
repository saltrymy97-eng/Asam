# services/receipts_service.py – سندات القبض والصرف الاحترافية (إصدار احترافي)
import sqlite3
from datetime import date
from database import get_connection
from services.audit_service import log_action
from services.accounting_service import save_journal_entry

def create_vouchers_table():
    """إنشاء جدول السندات إذا لم يكن موجوداً"""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            date TEXT NOT NULL,
            party_type TEXT NOT NULL,
            party_id INTEGER,
            amount REAL NOT NULL,
            account TEXT NOT NULL,
            invoice_id INTEGER,
            journal_entry_id INTEGER,
            reference TEXT,
            notes TEXT,
            created_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def get_cash_accounts():
    """جلب حسابات النقدية (المستوى الثاني تحت الأصول)"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    accounts = conn.execute("""
        SELECT code, name FROM accounts
        WHERE parent_id = (SELECT id FROM accounts WHERE code = '1')
        ORDER BY code
    """).fetchall()
    conn.close()
    if not accounts:
        return [{"code": "صندوق", "name": "صندوق"}, {"code": "بنك", "name": "بنك"}]
    return [{"code": a["code"], "name": a["name"]} for a in accounts]

def get_customers_with_balances():
    """جلب العملاء مع رصيدهم المستحق (إجمالي الفواتير - السندات)"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    customers = conn.execute("SELECT id, name FROM customers ORDER BY name").fetchall()
    result = []
    for c in customers:
        total_sales = conn.execute("""
            SELECT COALESCE(SUM(total), 0) FROM invoices
            WHERE type='sale' AND customer_id=? AND status='completed'
        """, (c["id"],)).fetchone()[0]
        total_receipts = conn.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM vouchers
            WHERE party_type='customer' AND party_id=?
        """, (c["id"],)).fetchone()[0]
        balance = total_sales - total_receipts
        result.append({"id": c["id"], "name": c["name"], "balance": balance})
    conn.close()
    return result

def get_suppliers_with_balances():
    """جلب الموردين مع رصيدهم المستحق (إجمالي فواتير الشراء - السندات)"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    suppliers = conn.execute("SELECT id, name FROM suppliers ORDER BY name").fetchall()
    result = []
    for s in suppliers:
        total_purchases = conn.execute("""
            SELECT COALESCE(SUM(total), 0) FROM invoices
            WHERE type='purchase' AND supplier_id=? AND status='completed'
        """, (s["id"],)).fetchone()[0]
        total_payments = conn.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM vouchers
            WHERE party_type='supplier' AND party_id=?
        """, (s["id"],)).fetchone()[0]
        balance = total_purchases - total_payments
        result.append({"id": s["id"], "name": s["name"], "balance": balance})
    conn.close()
    return result

def get_invoices_for_party(party_type, party_id):
    """جلب الفواتير المعلقة (غير المدفوعة بالكامل) للطرف"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    if party_type == 'customer':
        type_filter = 'sale'
        id_column = 'customer_id'
    else:
        type_filter = 'purchase'
        id_column = 'supplier_id'
    
    invoices = conn.execute(f"""
        SELECT id, invoice_date, total, 
               COALESCE((SELECT SUM(amount) FROM vouchers WHERE invoice_id = invoices.id), 0) as paid
        FROM invoices
        WHERE type=? AND {id_column}=? AND status='completed'
        ORDER BY invoice_date
    """, (type_filter, party_id)).fetchall()
    conn.close()
    pending = []
    for inv in invoices:
        remaining = inv["total"] - inv["paid"]
        if remaining > 0.01:
            pending.append({"id": inv["id"], "date": inv["invoice_date"], 
                            "total": inv["total"], "paid": inv["paid"], 
                            "remaining": remaining})
    return pending

def create_voucher(voucher_type, party_type, party_id, amount, account, 
                   invoice_id=None, reference="", notes="", created_by="admin", 
                   voucher_date=None):
    """
    إنشاء سند قبض أو صرف مع القيد المحاسبي
    """
    if voucher_date is None:
        voucher_date = date.today().strftime("%Y-%m-%d")
    
    create_vouchers_table()
    
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("BEGIN")
        
        cur = conn.execute("""
            INSERT INTO vouchers (type, date, party_type, party_id, amount, account, 
                                 invoice_id, reference, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (voucher_type, voucher_date, party_type, party_id, amount, account,
              invoice_id, reference, notes, created_by))
        voucher_id = cur.lastrowid
        
        if party_type == 'customer':
            party_name = conn.execute("SELECT name FROM customers WHERE id=?", 
                                     (party_id,)).fetchone()["name"]
        else:
            party_name = conn.execute("SELECT name FROM suppliers WHERE id=?", 
                                     (party_id,)).fetchone()["name"]
        
        if voucher_type == 'receipt':
            # قبض: مدين الصندوق، دائن العميل
            lines = [
                {"account": account, "debit": amount, "credit": 0},
                {"account": "113", "debit": 0, "credit": amount}  # العملاء
            ]
        else:
            # صرف: مدين المورد، دائن الصندوق
            lines = [
                {"account": "211", "debit": amount, "credit": 0},  # الموردون
                {"account": account, "debit": 0, "credit": amount}
            ]
        
        desc = f"سند {'قبض' if voucher_type == 'receipt' else 'صرف'} #{voucher_id} - {party_name}"
        if invoice_id:
            desc += f" (فاتورة #{invoice_id})"
            
        entry_id, error = save_journal_entry(
            description=desc,
            lines=lines,
            entry_date=voucher_date,
            conn=conn
        )
        if error:
            raise Exception(f"فشل القيد المحاسبي: {error}")
        
        conn.execute("UPDATE vouchers SET journal_entry_id=? WHERE id=?", 
                    (entry_id, voucher_id))
        
        # ✅ ربط السندات بوحدة الصندوق تلقائياً
        if account == "111":
            try:
                from services.cash_service import add_cash_transaction, get_all_cash_accounts
                cash_accounts = get_all_cash_accounts(active_only=True)
                if cash_accounts:
                    cash_acc = cash_accounts[0]  # أول حساب صندوق نشط
                    trans_type = "deposit" if voucher_type == "receipt" else "withdrawal"
                    add_cash_transaction(
                        cash_acc['id'],
                        voucher_date,
                        f"سند {'قبض' if voucher_type == 'receipt' else 'صرف'} #{voucher_id} - {party_name}",
                        trans_type,
                        amount
                    )
            except Exception:
                pass  # إذا فشلت حركة الصندوق، لا يؤثر على السند
        
        conn.commit()
        
        log_action(
            username=created_by,
            action=f"سند {'قبض' if voucher_type == 'receipt' else 'صرف'}",
            table_name="vouchers",
            record_id=voucher_id,
            new_value=f"{party_name}, المبلغ: {amount:,.2f}, {account}"
        )
        
        return voucher_id, None
    except Exception as e:
        conn.rollback()
        return None, str(e)
    finally:
        conn.close()

def get_vouchers(limit=50):
    """سجل السندات"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    vouchers = conn.execute("""
        SELECT v.*, 
               CASE WHEN v.party_type='customer' THEN c.name ELSE s.name END as party_name
        FROM vouchers v
        LEFT JOIN customers c ON v.party_type='customer' AND v.party_id = c.id
        LEFT JOIN suppliers s ON v.party_type='supplier' AND v.party_id = s.id
        ORDER BY v.id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(v) for v in vouchers]

def get_voucher_details(voucher_id):
    """تفاصيل سند مع القيد"""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    voucher = conn.execute("""
        SELECT v.*, 
               CASE WHEN v.party_type='customer' THEN c.name ELSE s.name END as party_name
        FROM vouchers v
        LEFT JOIN customers c ON v.party_type='customer' AND v.party_id = c.id
        LEFT JOIN suppliers s ON v.party_type='supplier' AND v.party_id = s.id
        WHERE v.id = ?
    """, (voucher_id,)).fetchone()
    if not voucher:
        conn.close()
        return None
    voucher = dict(voucher)
    entry_id = voucher.get("journal_entry_id")
    if entry_id:
        lines = conn.execute("""
            SELECT account_name, debit, credit FROM journal_lines WHERE entry_id=?
        """, (entry_id,)).fetchall()
        voucher["lines"] = [dict(l) for l in lines]
    conn.close()
    return voucher
