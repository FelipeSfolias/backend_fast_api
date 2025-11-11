# app/api/v1/students.py
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles
from app.models.student import Student as StudentModel
from app.schemas.student import Student, StudentCreate, StudentUpdate

router = APIRouter()

def _to_schema(s: StudentModel) -> Student:
    return Student(
        id=s.id,
        client_id=s.client_id,
        name=s.name,
        cpf=s.cpf,
        email=s.email,
        ra=s.ra,
        phone=s.phone,
        created_at=getattr(s, "created_at", None),
    )

@router.get("/", response_model=List[Student])
def list_students(
    q: Optional[str] = Query(None, description="Busca por nome, e-mail ou CPF"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    stmt = select(StudentModel).where(StudentModel.client_id == tenant.id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            (StudentModel.name.ilike(like)) |
            (StudentModel.email.ilike(like)) |
            (StudentModel.cpf.ilike(like))
        )
    stmt = stmt.order_by(StudentModel.id).offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(stmt).scalars().all()
    return [_to_schema(s) for s in rows]

<<<<<<< HEAD
@router.post("/",  dependencies=[Depends(require_roles("organizer","admin"))])
=======
@router.post("/", response_model=Student, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_roles("admin", "organizer"))])
>>>>>>> a4563aeb7b1c48000b196e1b282b41fdb48d1fc0
def create_student(
    body: StudentCreate,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    exists = db.execute(
        select(StudentModel).where(
            StudentModel.client_id == tenant.id,
            StudentModel.email == body.email
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado neste cliente")

    s = StudentModel(
        client_id=tenant.id,
        name=body.name,
        cpf=body.cpf,
        email=body.email,
        ra=body.ra,
        phone=body.phone,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _to_schema(s)

<<<<<<< HEAD
    obj = student_crud.create(db, body, extra={"client_id": tenant.id})
    return Student(id=obj.id, client_id=obj.client_id, name=obj.name, cpf=obj.cpf, email=obj.email, ra=obj.ra, phone=obj.phone)

@router.put("/{student_id}",    dependencies=[Depends(require_roles("organizer","admin"))])
def get_student(student_id: int, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    s = db.get(StudentModel, student_id)
    if not s or s.client_id != tenant.id: raise HTTPException(404)
    return Student(id=s.id, client_id=s.client_id, name=s.name, cpf=s.cpf, email=s.email, ra=s.ra, phone=s.phone)

@router.put("/{student_id}", response_model=Student, dependencies=[Depends(require_roles("admin","organizer"))])
def update_student(student_id: int, body: StudentUpdate, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    s = db.get(StudentModel, student_id)
    if not s or s.client_id != tenant.id: raise HTTPException(404)
    s = student_crud.update(db, s, body)
    return Student(id=s.id, client_id=s.client_id, name=s.name, cpf=s.cpf, email=s.email, ra=s.ra, phone=s.phone)

@router.delete("/{student_id}", dependencies=[Depends(require_roles("organizer","admin"))])
def delete_student(student_id: int, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    s = db.get(StudentModel, student_id)
    if not s or s.client_id != tenant.id: raise HTTPException(404)
    db.delete(s); db.commit()
    return {"ok": True}

@router.patch("/{student_id}")
def update_student(
    tenant = Depends(get_tenant),
    student_id: int = Path(...),
    payload: StudentUpdate = ...,
=======
@router.get("/{student_id}", response_model=Student)
def get_student(
    student_id: int = Path(..., ge=1),
>>>>>>> a4563aeb7b1c48000b196e1b282b41fdb48d1fc0
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    s = db.execute(
        select(StudentModel).where(
            StudentModel.id == student_id,
            StudentModel.client_id == tenant.id
        )
    ).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")
    return _to_schema(s)

@router.put("/{student_id}", response_model=Student,
            dependencies=[Depends(require_roles("admin", "organizer"))])
def update_student(
    student_id: int = Path(..., ge=1),
    body: StudentUpdate = None,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    s = db.execute(
        select(StudentModel).where(
            StudentModel.id == student_id,
            StudentModel.client_id == tenant.id
        )
    ).scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")

    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(s, k, v)

    db.add(s)
    db.commit()
    db.refresh(s)
    return _to_schema(s)

@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_roles("admin", "organizer"))])
def delete_student(
    student_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    s = db.execute(
        select(StudentModel).where(
            StudentModel.id == student_id,
            StudentModel.client_id == tenant.id
        )
    ).scalar_one_or_none()
    if not s:
        return
    db.delete(s)
    db.commit()
    return
