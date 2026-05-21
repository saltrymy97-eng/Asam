# api/routers/inventory.py
from fastapi import APIRouter, HTTPException
from typing import Optional
from services.inventory_service import (
    get_all_products,
    add_product,
    record_stock_movement,
    get_stock_movements,
    get_low_stock_products,
)

router = APIRouter(prefix="/inventory", tags=["Inventory"])

# ---------- المنتجات ----------
@router.get("/products")
async def list_products():
    """جلب جميع المنتجات"""
    products = get_all_products()
    return products

@router.post("/products")
async def create_product(
    name: str,
    barcode: Optional[str] = None,
    category: str = "أخرى",
    purchase_price: float = 0.0,
    selling_price: float = 0.0,
    quantity: int = 0,
    reorder_level: int = 10
):
    """إضافة منتج جديد"""
    success, error = add_product(
        name=name,
        barcode=barcode,
        category=category,
        purchase_price=purchase_price,
        selling_price=selling_price,
        quantity=quantity,
        reorder_level=reorder_level,
        username="api_user"
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"message": f"تم إضافة المنتج '{name}' بنجاح", "success": success}

# ---------- حركات المخزون ----------
@router.post("/stock-movements")
async def create_stock_movement(
    product_id: int,
    product_name: str,
    move_type: str,
    quantity: int,
    reference: str = ""
):
    """تسجيل حركة مخزون (داخل/خارج)"""
    success, error = record_stock_movement(
        product_id=product_id,
        product_name=product_name,
        move_type=move_type,
        quantity=quantity,
        reference=reference,
        username="api_user"
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"message": "تم تسجيل الحركة بنجاح", "success": success}

@router.get("/stock-movements")
async def list_stock_movements(limit: int = 50):
    """جلب آخر حركات المخزون"""
    movements = get_stock_movements(limit=limit)
    return movements

# ---------- تنبيهات النقص ----------
@router.get("/low-stock")
async def low_stock_products():
    """المنتجات تحت الحد الأدنى"""
    products = get_low_stock_products()
    return products
