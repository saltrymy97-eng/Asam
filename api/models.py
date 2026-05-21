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

# ========== نماذج المخزون ==========
class ProductCreate(BaseModel):
    name: str
    barcode: Optional[str] = None
    category: str = "أخرى"
    purchase_price: float = 0.0
    selling_price: float = 0.0
    quantity: int = 0
    reorder_level: int = 10

class StockMovementCreate(BaseModel):
    product_id: int
    product_name: str
    move_type: str
    quantity: int
    reference: str = ""

# ========== نماذج الموارد البشرية ==========
class EmployeeCreate(BaseModel):
    name: str
    position: str = ""
    salary: float = 0.0
    join_date: str = ""

class AttendanceCreate(BaseModel):
    employee_id: int
    employee_name: str
    date: str
    status: str = "حاضر"

# ========== نماذج الحسابات ==========
class JournalEntryLine(BaseModel):
    account: str
    debit: float = 0.0
    credit: float = 0.0

class JournalEntryCreate(BaseModel):
    description: str
    lines: List[JournalEntryLine]
    entry_date: Optional[str] = None

class JournalEntryResponse(BaseModel):
    entry_id: int
    message: str
