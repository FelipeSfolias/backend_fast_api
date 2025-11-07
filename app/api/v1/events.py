# app/api/v1/events.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_db, get_current_user_scoped
from app.api.permissions import Role, require_roles, require_role_at_least
from app.schemas.user import UserOut
from app.models.event import Event  # ajuste ao seu modelo
from pydantic import BaseModel

class EventCreate(BaseModel):
    name: str
    starts_at: str
    ends_at: str
    location: str
    description: str | None = None

class EventOut(BaseModel):
    id: int
    name: str
    starts_at: str
    ends_at: str
    location: str
    description: str | None = None

    class Config:
        from_attributes = True

router = APIRouter()

@router.get("/", response_model=List[EventOut])
def list_events(
    db: Session = Depends(get_db),
    _: UserOut = Depends(get_current_user_scoped),  # todos perfis autenticados
):
    rows = db.execute(select(Event)).scalars().all()
    return rows

@router.get("/{event_id}", response_model=EventOut)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: UserOut = Depends(get_current_user_scoped),  # todos perfis autenticados
):
    obj = db.get(Event, event_id)
    if not obj:
        raise HTTPException(404, "Evento não encontrado")
    return obj

@router.post("/", response_model=EventOut, dependencies=[Depends(require_roles([Role.ORGANIZADOR, Role.ADMIN_CLIENTE]))])
def create_event(
    data: EventCreate,
    db: Session = Depends(get_db),
    _: UserOut = Depends(get_current_user_scoped),
):
    obj = Event(
        name=data.name,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        location=data.location,
        description=data.description,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.put("/{event_id}", response_model=EventOut, dependencies=[Depends(require_roles([Role.ORGANIZADOR, Role.ADMIN_CLIENTE]))])
def update_event(
    event_id: int,
    data: EventCreate,
    db: Session = Depends(get_db),
    _: UserOut = Depends(get_current_user_scoped),
):
    obj = db.get(Event, event_id)
    if not obj:
        raise HTTPException(404, "Evento não encontrado")
    obj.name = data.name
    obj.starts_at = data.starts_at
    obj.ends_at = data.ends_at
    obj.location = data.location
    obj.description = data.description
    db.commit()
    db.refresh(obj)
    return obj

@router.delete("/{event_id}", dependencies=[Depends(require_roles([Role.ORGANIZADOR, Role.ADMIN_CLIENTE]))])
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: UserOut = Depends(get_current_user_scoped),
):
    obj = db.get(Event, event_id)
    if not obj:
        raise HTTPException(404, "Evento não encontrado")
    db.delete(obj)
    db.commit()
    return {"ok": True}
