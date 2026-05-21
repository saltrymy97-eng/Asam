# api/models.py
from pydantic import BaseModel
from typing import List, Optional

# ========== نماذج المبيعات ==========
class SaleItem(BaseModel):
    product_id: int
    quantity: int
    unit_price: float

class SaleInvoiceCreate(BaseModel):
    customer_id: int
    items: List[SaleItem]

class SaleInvoiceResponse(BaseModel):
    invoice_id: int
    total: float
    message: str

# ========== نماذج المشتريات ==========
class PurchaseItem(BaseModel):
    product_id: int
    quantity: int
    unit_price: float

class PurchaseInvoiceCreate(BaseModel):
    supplier_id: int
    items: List[PurchaseItem]

class PurchaseInvoiceResponse(BaseModel):
    invoice_id: int
    total: float
    message: str
