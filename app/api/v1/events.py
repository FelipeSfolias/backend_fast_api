from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Any, Dict, List
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles
from app.schemas.event import Event, EventCreate, EventUpdate
from app.schemas.day_event import DayEvent, DayEventCreate, DayEventUpdate
from app.crud.event import event_crud
from app.crud.day_event import day_event_crud
from app.models.event import Event as EventModel
from app.models.day_event import DayEvent as DayModel
from fastapi import APIRouter, Depends, HTTPException, Path,Body, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Body, status
from datetime import date, time


router = APIRouter()

@router.get("/")
def list_events(db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    rows = db.execute(select(EventModel).where(EventModel.client_id==tenant.id)).scalars().all()
    return [Event(id=e.id, client_id=e.client_id, **{k:getattr(e,k) for k in ("title","description","venue","capacity_total","workload_hours","min_presence_pct","start_at","end_at","status")}) for e in rows]

@router.post("/", dependencies=[Depends(require_roles("organizer","admin"))])
def create_event(body: EventCreate, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    e = event_crud.create(db, body, extra={"client_id": tenant.id})
    return Event(id=e.id, client_id=e.client_id, **body.model_dump())

@router.get("/{event_id}")
def get_event(event_id: int, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    e = db.get(EventModel, event_id)
    if not e or e.client_id != tenant.id: raise HTTPException(404)
    return Event(id=e.id, client_id=e.client_id, **{k:getattr(e,k) for k in ("title","description","venue","capacity_total","workload_hours","min_presence_pct","start_at","end_at","status")})

@router.post("/{event_id}/days", dependencies=[Depends(require_roles("organizer","admin"))])
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

# substitua o SEU @router.put("/events/{event_id}") por este:
@router.put("/{event_id}/days/{day_id}", dependencies=[Depends(require_roles("organizer","admin"))])
def update_event(
    event_id: int,
    body: EventUpdate = Body(...),            # usa seu schema de update
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    # carrega o evento e valida tenant
    e = db.get(EventModel, event_id)
    if not e or e.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    # aplica apenas os campos enviados
    data = body.model_dump(exclude_unset=True)
    allowed = {"title","description","venue","capacity_total","workload_hours","min_presence_pct","start_at","end_at","status"}
    changed = False
    for k, v in data.items():
        if k in allowed and hasattr(e, k):
            setattr(e, k, v)
            changed = True

    if not changed:
        raise HTTPException(status_code=400, detail="Nenhum campo válido para atualização")

    db.add(e)
    db.commit()
    db.refresh(e)

    return Event(
        id=e.id,
        client_id=e.client_id,
        title=e.title,
        description=e.description,
        venue=e.venue,
        capacity_total=e.capacity_total,
        workload_hours=e.workload_hours,
        min_presence_pct=e.min_presence_pct,
        start_at=e.start_at,
        end_at=e.end_at,
        status=e.status,
    )


# substitua o SEU @router.delete("/events/{event_id}", ...) por este:
@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_roles("admin","organizer"))])
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    e = db.get(EventModel, event_id)
    if not e or e.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    db.delete(e)
    db.commit()
    return None  # 204

@router.put("/{event_id}/days/{day_id}",
            response_model=DayEvent,
            dependencies=[Depends(require_roles("admin","organizer"))])
def update_day(
    event_id: int,
    day_id: int,
    body: DayEventUpdate = Body(...),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    # garante que o evento existe e é do tenant
    e = db.get(EventModel, event_id)
    if not e or e.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    # carrega o dia do próprio evento
    d = db.get(DayModel, day_id)
    if not d or d.event_id != e.id:
        raise HTTPException(status_code=404, detail="Dia do evento não encontrado")

    # aplica somente campos enviados
    data = body.model_dump(exclude_unset=True)
    allowed = {"date", "start_time", "end_time", "room", "capacity"}
    changed = False
    for k, v in data.items():
        if k in allowed and hasattr(d, k):
            setattr(d, k, v)
            changed = True

    if not changed:
        raise HTTPException(status_code=400, detail="Nenhum campo válido para atualização")

    db.add(d)
    db.commit()
    db.refresh(d)

    return DayEvent(
        id=d.id,
        event_id=d.event_id,
        date=d.date,
        start_time=d.start_time,
        end_time=d.end_time,
        room=d.room,
        capacity=d.capacity,
    )


@router.delete("/{event_id}/days/{day_id}",
               status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_roles("admin","organizer"))])
def delete_day(
    event_id: int,
    day_id: int,
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    # garante que o evento existe e é do tenant
    e = db.get(EventModel, event_id)
    if not e or e.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    # carrega o dia do próprio evento
    d = db.get(DayModel, day_id)
    if not d or d.event_id != e.id:
        raise HTTPException(status_code=404, detail="Dia do evento não encontrado")

    db.delete(d)
    db.commit()
    return None
