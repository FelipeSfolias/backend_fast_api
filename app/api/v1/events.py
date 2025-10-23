from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Any, Dict, List
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles
from app.schemas.event import Event, EventCreate, EventUpdate
from app.schemas.day_event import DayEvent, DayEventCreate
from app.crud.event import event_crud
from app.crud.day_event import day_event_crud
from app.models.event import Event as EventModel
from app.models.day_event import DayEvent as DayModel
from fastapi import APIRouter, Depends, HTTPException, Path,Body, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

router = APIRouter()

@router.get("/", response_model=List[Event])
def list_events(db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    rows = db.execute(select(EventModel).where(EventModel.client_id==tenant.id)).scalars().all()
    return [Event(id=e.id, client_id=e.client_id, **{k:getattr(e,k) for k in ("title","description","venue","capacity_total","workload_hours","min_presence_pct","start_at","end_at","status")}) for e in rows]

@router.post("/", response_model=Event, status_code=201, dependencies=[Depends(require_roles("admin","organizer"))])
def create_event(body: EventCreate, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    e = event_crud.create(db, body, extra={"client_id": tenant.id})
    return Event(id=e.id, client_id=e.client_id, **body.model_dump())

@router.get("/{event_id}", response_model=Event)
def get_event(event_id: int, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    e = db.get(EventModel, event_id)
    if not e or e.client_id != tenant.id: raise HTTPException(404)
    return Event(id=e.id, client_id=e.client_id, **{k:getattr(e,k) for k in ("title","description","venue","capacity_total","workload_hours","min_presence_pct","start_at","end_at","status")})

@router.post("/{event_id}/days", response_model=DayEvent, status_code=201, dependencies=[Depends(require_roles("admin","organizer"))])
def add_day(event_id: int, body: DayEventCreate, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    e = db.get(EventModel, event_id)
    if not e or e.client_id != tenant.id: raise HTTPException(404)
    d = day_event_crud.create(db, body, extra={"event_id": e.id})
    return DayEvent(id=d.id, event_id=e.id, **body.model_dump())

@router.get("/{event_id}/days", response_model=List[DayEvent])
def list_days(event_id: int, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    e = db.get(EventModel, event_id)
    if not e or e.client_id != tenant.id: raise HTTPException(404)
    rows = db.execute(select(DayModel).where(DayModel.event_id==e.id)).scalars().all()
    return [DayEvent(id=d.id, event_id=e.id, date=d.date, start_time=d.start_time, end_time=d.end_time, room=d.room, capacity=d.capacity) for d in rows]

class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    venue: str | None = None
    capacity_total: int | None = None
    workload_hours: int | None = None
    min_presence_pct: int | None = None
    start_at: str | None = None
    end_at: str | None = None
    status: str | None = None
    class Config:
        from_attributes = True

@router.put("/events/{event_id}")
def update_event(
    event_id: int,
    payload: Dict[str, Any] = Body(...),   # aceita JSON parcial: {"description": "..."} etc.
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    # Carrega o evento do tenant atual
    stmt = select(Event).where(
        Event.id == event_id,
        Event.client.has(slug=tenant.slug)    # <- multi-tenant pelo slug (estável)
    )
    event = db.execute(stmt).scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    # Campos que permitimos atualizar
    ALLOWED_FIELDS = {
        "name", "title",
        "description", "location",
        "starts_at", "ends_at", "start_date", "end_date",
        "is_active", "capacity",
    }

    # Aplique somente os campos permitidos e existentes no modelo
    changed = False
    for key, value in (payload or {}).items():
        if key in ALLOWED_FIELDS and hasattr(event, key):
            setattr(event, key, value)
            changed = True

    if not changed:
        # Nada aplicável no corpo
        raise HTTPException(status_code=400, detail="Nenhum campo válido para atualização")

    db.add(event)
    db.commit()
    db.refresh(event)

    # Retorne o próprio objeto (se houver schema de saída, pode usar response_model)
    return {
        "id": event.id,
        "name": getattr(event, "name", None) or getattr(event, "title", None),
        "description": getattr(event, "description", None),
        "location": getattr(event, "location", None),
        "starts_at": getattr(event, "starts_at", None) or getattr(event, "start_date", None),
        "ends_at": getattr(event, "ends_at", None) or getattr(event, "end_date", None),
        "is_active": getattr(event, "is_active", None),
        "capacity": getattr(event, "capacity", None),
        "client_id": getattr(event, "client_id", None),
    }

@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
):
    stmt = select(Event).where(
        Event.id == event_id,
        Event.client.has(slug=tenant.slug)
    )
    event = db.execute(stmt).scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    db.delete(event)
    db.commit()
    return None  # 204 No Content
