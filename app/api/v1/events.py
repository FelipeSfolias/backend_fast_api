# app/api/v1/events.py
from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Body, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles, ROLE_ADMIN, ROLE_ORGANIZER
from app.models.event import Event as EventModel
from app.schemas.event import Event as EventOut, EventCreate, EventUpdate

router = APIRouter()

@router.get("/", response_model=List[EventOut])
def list_events(
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),  # qualquer perfil autenticado
):
    rows = db.execute(select(EventModel).where(EventModel.client_id == tenant.id)).scalars().all()
    return rows

@router.get("/{event_id}", response_model=EventOut)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    obj = db.get(EventModel, event_id)
    if not obj or obj.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    return obj

@router.post("/", response_model=EventOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ORGANIZER))])
def create_event(
    body: EventCreate = Body(...),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    obj = EventModel(client_id=tenant.id, **body.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.put("/{event_id}", response_model=EventOut,
            dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ORGANIZER))])
def update_event(
    event_id: int,
    body: EventUpdate = Body(...),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    obj = db.get(EventModel, event_id)
    if not obj or obj.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    data = body.model_dump(exclude_unset=True)
    for k,v in data.items():
        setattr(obj, k, v)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_roles(ROLE_ADMIN, ROLE_ORGANIZER))])
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    obj = db.get(EventModel, event_id)
    if not obj or obj.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    db.delete(obj); db.commit()
    return None
