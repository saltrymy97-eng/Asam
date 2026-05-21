# api/routers/accounting.py
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from services.accounting_service import (
    save_journal_entry,
    get_recent_entries,
    get_entry_details,
    get_ledger,
    get_trial_balance,
)

router = APIRouter(prefix="/accounting", tags=["Accounting"])

# ---------- قيود اليومية ----------
@router.post("/entries")
async def create_entry(
    description: str,
    lines: List[dict],
    entry_date: Optional[str] = None
):
    """تسجيل قيد يومية جديد"""
    entry_id, error = save_journal_entry(
        description=description,
        lines=lines,
        entry_date=entry_date
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"message": f"تم تسجيل القيد رقم {entry_id} بنجاح", "entry_id": entry_id}

@router.get("/entries")
async def list_entries(limit: int = 10):
    """آخر قيود اليومية"""
    entries = get_recent_entries(limit=limit)
    return entries

@router.get("/entries/{entry_id}")
async def entry_details(entry_id: int):
    """تفاصيل قيد محدد"""
    details = get_entry_details(entry_id)
    if not details:
        raise HTTPException(status_code=404, detail="القيد غير موجود")
    return details

# ---------- دفتر الأستاذ ----------
@router.get("/ledger/{account_name}")
async def account_ledger(account_name: str):
    """دفتر الأستاذ لحساب محدد"""
    ledger = get_ledger(account_name)
    return ledger

# ---------- ميزان المراجعة ----------
@router.get("/trial-balance")
async def trial_balance():
    """ميزان المراجعة"""
    tb = get_trial_balance()
    return tb
