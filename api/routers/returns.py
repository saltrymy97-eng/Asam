# api/routers/returns.py
from fastapi import APIRouter, HTTPException
from typing import List
from services.returns_service import (
    get_sales_invoices,
    get_purchase_invoices,
    get_invoice_items,
    process_return,
    get_return_history,
)

router = APIRouter(prefix="/returns", tags=["Returns"])

# ---------- فواتير قابلة للإرجاع ----------
@router.get("/sales-invoices")
async def list_sales_invoices():
    """جلب فواتير المبيعات المكتملة (القابلة للإرجاع)"""
    invoices = get_sales_invoices()
    return invoices

@router.get("/purchase-invoices")
async def list_purchase_invoices():
    """جلب فواتير المشتريات المكتملة (القابلة للإرجاع)"""
    invoices = get_purchase_invoices()
    return invoices

# ---------- بنود الفاتورة ----------
@router.get("/invoice-items/{invoice_id}")
async def invoice_items(invoice_id: int):
    """جلب بنود فاتورة محددة"""
    items = get_invoice_items(invoice_id)
    if not items:
        raise HTTPException(status_code=404, detail="الفاتورة غير موجودة أو ليس لها بنود")
    return items

# ---------- تنفيذ المرتجع ----------
@router.post("/process")
async def create_return(
    invoice_type: str,
    invoice_id: int,
    items_to_return: List[dict],
    return_date: str,
    reason: str = ""
):
    """
    تنفيذ عملية مرتجع (مبيعات أو مشتريات)
    invoice_type: 'sale' أو 'purchase'
    items_to_return: قائمة تحتوي على [{"name": "اسم المنتج", "quantity": الكمية}]
    """
    if invoice_type not in ["sale", "purchase"]:
        raise HTTPException(status_code=400, detail="نوع الفاتورة يجب أن يكون 'sale' أو 'purchase'")
    
    # تحويل items_to_return إلى الصيغة المطلوبة
    items = [(item["name"], item["quantity"]) for item in items_to_return]
    
    success, result, total = process_return(
        invoice_type=invoice_type,
        invoice_id=invoice_id,
        items_to_return=items,
        return_date=return_date,
        reason=reason
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=result)
    
    return {
        "message": f"تم تسجيل المرتجع رقم {result} بنجاح",
        "return_id": result,
        "total": total
    }

# ---------- سجل المرتجعات ----------
@router.get("/history")
async def return_history():
    """جلب سجل المرتجعات"""
    returns = get_return_history()
    return returns
