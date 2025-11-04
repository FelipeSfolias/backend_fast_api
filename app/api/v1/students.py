from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.schemas.student import Student, StudentCreate, StudentUpdate
from app.crud.student import student_crud
from app.core.rbac import require_roles
from app.models.student import Student as StudentModel
from sqlalchemy import select
from app.models.student import Student as StudentModel
from fastapi import HTTPException, status
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/")
def list_students(q: str | None = Query(None), page: int = 1, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    stmt = select(StudentModel).where(StudentModel.client_id==tenant.id)
    if q:
        stmt = stmt.where(StudentModel.name.ilike(f"%{q}%"))
    return [Student(id=s.id, client_id=s.client_id, name=s.name, cpf=s.cpf, email=s.email, ra=s.ra, phone=s.phone) for s in db.execute(stmt).scalars().all()]

@router.post("/")
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,   # <- sem parênteses!
            detail={
                "code": "STUDENT_EMAIL_EXISTS",
                "message": "E-mail já cadastrado para este cliente.",
                "details": {"email": body.email}
            },
        )

    obj = student_crud.create(db, body, extra={"client_id": tenant.id})
    return Student(id=obj.id, client_id=obj.client_id, name=obj.name, cpf=obj.cpf, email=obj.email, ra=obj.ra, phone=obj.phone)
@router.get("/{student_id}", response_model=Student)
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

@router.delete("/{student_id}", dependencies=[Depends(require_roles("admin","organizer"))])
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
    db: Session = Depends(get_db),
    _user = Depends(get_current_user_scoped),
):
    st = db.get(Student, student_id)
    if not st or st.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Student not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(st, k, v)

    db.add(st)
    db.commit()
    db.refresh(st)

    return {
        "id": st.id,
        "client_id": st.client_id,
        "name": st.name,
        "cpf": st.cpf,
        "email": st.email,
        "ra": st.ra,
        "phone": st.phone,
    }

