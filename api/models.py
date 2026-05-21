# api/models.py
from pydantic import BaseModel
from typing import List, Optional

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
