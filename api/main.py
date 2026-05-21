# api/main.py
from fastapi import FastAPI
from api.routers import sales, inventory, purchases, hr, accounting, returns
from scalar_fastapi import get_scalar_api_reference

app = FastAPI(
    title="XD ERP API",
    description="واجهة برمجة تطبيقات لنظام XD ERP",
    version="1.0.0",
)

# تضمين جميع نقاط النهاية
app.include_router(sales.router)
app.include_router(inventory.router)
app.include_router(purchases.router)
app.include_router(hr.router)
app.include_router(accounting.router)
app.include_router(returns.router)

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "مرحباً بك في XD ERP API"}

# 🆕 نقطة نهاية لواجهة Scalar الجميلة
@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )
