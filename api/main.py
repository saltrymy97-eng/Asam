# api/main.py
from fastapi import FastAPI
from api.routers import sales, inventory

app = FastAPI(
    title="XD ERP API",
    description="واجهة برمجة تطبيقات لنظام XD ERP",
    version="1.0.0",
)

app.include_router(sales.router)
app.include_router(inventory.router)

@app.get("/")
async def root():
    return {"message": "مرحباً بك في XD ERP API"}
