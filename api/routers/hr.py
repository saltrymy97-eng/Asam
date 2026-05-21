# api/routers/hr.py
from fastapi import APIRouter, HTTPException
from services.hr_service import (
    get_all_employees,
    add_employee,
    get_employees_for_select,
    record_attendance,
    get_attendance_history,
)

router = APIRouter(prefix="/hr", tags=["HR"])

# ---------- الموظفين ----------
@router.get("/employees")
async def list_employees():
    """جلب جميع الموظفين"""
    employees = get_all_employees()
    return employees

@router.post("/employees")
async def create_employee(
    name: str,
    position: str = "",
    salary: float = 0.0,
    join_date: str = ""
):
    """إضافة موظف جديد"""
    success, error = add_employee(
        name=name,
        position=position,
        salary=salary,
        join_date=join_date,
        username="api_user"
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"message": f"تم إضافة الموظف '{name}' بنجاح", "success": success}

# ---------- الحضور والانصراف ----------
@router.post("/attendance")
async def create_attendance(
    employee_id: int,
    employee_name: str,
    date: str,
    status: str = "حاضر"
):
    """تسجيل حضور وانصراف"""
    success, error = record_attendance(
        employee_id=employee_id,
        employee_name=employee_name,
        date_str=date,
        status=status,
        username="api_user"
    )
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"message": "تم تسجيل الحضور بنجاح", "success": success}

@router.get("/attendance")
async def list_attendance():
    """جلب سجل الحضور"""
    attendance = get_attendance_history()
    return attendance
