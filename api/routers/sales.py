# api/routers/sales.py
from fastapi import APIRouter, HTTPException
from api.models import SaleInvoiceCreate, SaleInvoiceResponse
import sqlite3
from datetime import date

DB_PATH = "erp.db"

router = APIRouter(prefix="/sales", tags=["Sales"])

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@router.post("/invoices", response_model=SaleInvoiceResponse)
async def create_invoice(invoice: SaleInvoiceCreate):
    """إنشاء فاتورة مبيعات جديدة"""
    try:
        conn = get_conn()
        total = sum(item.quantity * item.unit_price for item in invoice.items)
        
        cur = conn.execute(
            "INSERT INTO invoices (type, party_id, invoice_date, total, status) VALUES ('sale', ?, date('now'), ?, 'completed')",
            (invoice.customer_id, total)
        )
        invoice_id = cur.lastrowid
        
        for item in invoice.items:
            conn.execute(
                "INSERT INTO invoice_items (invoice_id, product_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                (invoice_id, item.product_id, item.quantity, item.unit_price)
            )
        
        conn.commit()
        conn.close()
        
        return SaleInvoiceResponse(
            invoice_id=invoice_id,
            total=total,
            message="تم إنشاء الفاتورة بنجاح"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/invoices")
async def list_invoices():
    """جلب جميع فواتير المبيعات"""
    conn = get_conn()
    invoices = conn.execute("""
        SELECT i.id, c.name as customer, i.invoice_date, i.total, i.status
        FROM invoices i
        LEFT JOIN customers c ON i.party_id = c.id
        WHERE i.type = 'sale'
        ORDER BY i.id DESC
    """).fetchall()
    conn.close()
    return [dict(inv) for inv in invoices]

@router.get("/invoices/{invoice_id}")
async def invoice_details(invoice_id: int):
    """جلب تفاصيل فاتورة محددة"""
    conn = get_conn()
    details = conn.execute("""
        SELECT p.name, ii.quantity, ii.unit_price, (ii.quantity * ii.unit_price) as total
        FROM invoice_items ii
        JOIN products p ON ii.product_id = p.id
        WHERE ii.invoice_id = ?
    """, (invoice_id,)).fetchall()
    conn.close()
    if not details:
        raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")
    return [dict(d) for d in details]
