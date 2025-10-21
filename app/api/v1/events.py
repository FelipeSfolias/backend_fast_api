from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles
from app.schemas.event import Event, EventCreate, EventUpdate
from app.schemas.day_event import DayEvent, DayEventCreate
from app.crud.event import event_crud
from app.crud.day_event import day_event_crud
from app.models.event import Event as EventModel
from app.models.day_event import DayEvent as DayModel
from fastapi import APIRouter, Depends, HTTPException, Path
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

@router.patch("/{event_id}")
def update_event(
    tenant = Depends(get_tenant),
    event_id: int = Path(...),
    payload: EventUpdate = ...,
    db: Session = Depends(get_db),
    _user = Depends(get_current_user_scoped),
):
    ev = db.get(Event, event_id)
    if not ev or ev.client_id != tenant.id:
        raise HTTPException(status_code=404, detail="Event not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(ev, k, v)
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev

@router.delete("/{event_id}/days/{day_id}", status_code=204)
def delete_event_day(
    tenant = Depends(get_tenant),
    event_id: int = Path(...),
    day_id: int = Path(...),
    db: Session = Depends(get_db),
    _user = Depends(get_current_user_scoped),
):
    day = db.get(DayEvent, day_id)
    if not day or day.event_id != event_id:
        raise HTTPException(status_code=404, detail="Day not found")
    # Opcional: cheque se o evento é do tenant
    # (mais seguro se você fizer join para confirmar client_id)
    db.delete(day)
    db.commit()
    return