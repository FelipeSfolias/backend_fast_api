# app/api/v1/students.py
from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Body, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles, ROLE_ADMIN, ROLE_ORGANIZER
from app.models.student import Student as StudentModel
from app.schemas.student import Student as StudentOut, StudentCreate, StudentUpdate

router = APIRouter()

@router.get("/", response_model=List[StudentOut])
def list_students(
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    rows = db.execute(select(StudentModel).where(StudentModel.client_id == tenant.id)).scalars().all()
    return rows

@router.post("/", response_model=StudentOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ORGANIZER))])
def create_student(
    body: StudentCreate = Body(...),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    obj = StudentModel(client_id=tenant.id, **body.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.put("/{student_id}", response_model=StudentOut,
            dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ORGANIZER))])
def update_student(
    student_id: int,
    body: StudentUpdate = Body(...),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    st = db.get(StudentModel, student_id)
    if not st or st.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Student não encontrado")
    data = body.model_dump(exclude_unset=True)
    for k,v in data.items():
        setattr(st,k,v)
    db.add(st); db.commit(); db.refresh(st)
    return st

@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ORGANIZER))])
def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    st = db.get(StudentModel, student_id)
    if not st or st.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Student não encontrado")
    db.delete(st); db.commit()
    return None
