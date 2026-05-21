# api/routers/sales.py
from fastapi import APIRouter, HTTPException
from api.models import SaleInvoiceCreate, SaleInvoiceResponse
from services.sales_service import (
    create_sale_invoice,
    get_sale_invoices,
    get_invoice_details,
)

router = APIRouter(prefix="/sales", tags=["Sales"])

@router.post("/invoices", response_model=SaleInvoiceResponse)
async def create_invoice(invoice: SaleInvoiceCreate):
    """إنشاء فاتورة مبيعات جديدة"""
    items = [item.model_dump() for item in invoice.items]
    invoice_id, total, error = create_sale_invoice(
        customer_id=invoice.customer_id,
        items=items,
        username="api_user"
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return SaleInvoiceResponse(
        invoice_id=invoice_id,
        total=total,
        message="تم إنشاء الفاتورة بنجاح"
    )

@router.get("/invoices")
async def list_invoices():
    """جلب جميع فواتير المبيعات"""
    invoices = get_sale_invoices()
    return invoices

@router.get("/invoices/{invoice_id}")
async def invoice_details(invoice_id: int):
    """جلب تفاصيل فاتورة محددة"""
    details = get_invoice_details(invoice_id)
    if not details:
        raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")
    return details
