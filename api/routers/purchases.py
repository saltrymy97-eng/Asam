# api/routers/purchases.py
from fastapi import APIRouter, HTTPException
from api.models import PurchaseInvoiceCreate, PurchaseInvoiceResponse
from services.purchases_service import (
    get_suppliers,
    create_purchase_invoice,
    get_purchase_invoices,
    get_invoice_details,
    add_supplier,
    get_all_suppliers,
)

router = APIRouter(prefix="/purchases", tags=["Purchases"])

# ---------- فواتير المشتريات ----------
@router.post("/invoices", response_model=PurchaseInvoiceResponse)
async def create_invoice(invoice: PurchaseInvoiceCreate):
    """إنشاء فاتورة مشتريات جديدة"""
    items = [item.model_dump() for item in invoice.items]
    invoice_id, total, error = create_purchase_invoice(
        supplier_id=invoice.supplier_id,
        items=items,
        username="api_user"
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return PurchaseInvoiceResponse(
        invoice_id=invoice_id,
        total=total,
        message="تم إنشاء فاتورة المشتريات بنجاح"
    )

@router.get("/invoices")
async def list_invoices():
    """جلب جميع فواتير المشتريات"""
    invoices = get_purchase_invoices()
    return invoices

@router.get("/invoices/{invoice_id}")
async def invoice_details(invoice_id: int):
    """جلب تفاصيل فاتورة شراء محددة"""
    details = get_invoice_details(invoice_id)
    if not details:
        raise HTTPException(status_code=404, detail="الفاتورة غير موجودة")
    return details

# ---------- الموردين ----------
@router.get("/suppliers")
async def list_suppliers():
    """جلب جميع الموردين"""
    suppliers = get_all_suppliers()
    return suppliers

@router.post("/suppliers")
async def create_supplier(
    name: str,
    phone: str = "",
    address: str = ""
):
    """إضافة مورد جديد"""
    add_supplier(
        name=name,
        phone=phone,
        address=address,
        username="api_user"
    )
    return {"message": f"تم إضافة المورد '{name}' بنجاح"}
