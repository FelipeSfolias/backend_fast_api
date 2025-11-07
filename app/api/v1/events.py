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
from fastapi import APIRouter, Depends, HTTPException, Query, Path
import sqlalchemy as sa


router = APIRouter()

@router.get("/")
def list_events(db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    rows = db.execute(select(EventModel).where(EventModel.client_id==tenant.id)).scalars().all()
    return [Event(id=e.id, client_id=e.client_id, **{k:getattr(e,k) for k in ("title","description","venue","capacity_total","workload_hours","min_presence_pct","start_at","end_at","status")}) for e in rows]

@router.post("/")
def create_event(body: EventCreate, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    e = event_crud.create(db, body, extra={"client_id": tenant.id})
    return Event(id=e.id, client_id=e.client_id, **body.model_dump())

@router.get("/{event_id}")
def get_event(event_id: int, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    e = db.get(EventModel, event_id)
    if not e or e.client_id != tenant.id: raise HTTPException(404)
    return Event(id=e.id, client_id=e.client_id, **{k:getattr(e,k) for k in ("title","description","venue","capacity_total","workload_hours","min_presence_pct","start_at","end_at","status")})

@router.post("/{event_id}/days")
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
@router.put("/{event_id}", response_model=Event, dependencies=[Depends(require_roles("admin","organizer"))])
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


@router.delete("/{event_id}", dependencies=[Depends(require_roles("admin", "organizer"))])
def delete_event(
    event_id: int = Path(..., ge=1),
    force: bool = Query(False, description="Se true, apaga em cascata vínculos (inscrições, presenças etc.)"),
    db: Session = Depends(get_db),
    tenant = Depends(get_tenant),
    _ = Depends(get_current_user_scoped),
):
    # 1) evento do tenant?
    ev = db.execute(
        select(Event).where(Event.id == event_id, Event.client_id == tenant.id)
    ).scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")

    # 2) se não for force, checa refs e bloqueia com 409 amigável
    if not force:
        has_refs = db.execute(sa.text("""
            SELECT
              EXISTS (SELECT 1 FROM enrollments WHERE event_id = :e) OR
              EXISTS (SELECT 1 FROM day_events  WHERE event_id = :e)
        """), {"e": event_id}).scalar()
        if has_refs:
            raise HTTPException(
                status_code=409,
                detail="Evento possui inscrições ou dias associados. Use ?force=1 para apagar em cascata."
            )

    # 3) cascade manual (ordem importa). Usa SQL Core pra não depender de todos os models.
    params = {"e": event_id, "c": tenant.id}

    # attendances via enrollment ou via day_event
    res_att = db.execute(sa.text("""
        DELETE FROM attendances
        WHERE enrollment_id IN (SELECT id FROM enrollments WHERE event_id = :e)
           OR day_event_id IN (SELECT id FROM day_events  WHERE event_id = :e)
    """), params)

    # certificates das inscrições do evento
    res_cert = db.execute(sa.text("""
        DELETE FROM certificates
        USING enrollments
        WHERE certificates.enrollment_id = enrollments.id
          AND enrollments.event_id = :e
    """), params)

    # enrollments do evento
    res_enr = db.execute(sa.text("DELETE FROM enrollments WHERE event_id = :e"), params)

    # day_events do evento
    res_days = db.execute(sa.text("DELETE FROM day_events WHERE event_id = :e"), params)

    # finalmente, o próprio evento (scoped ao tenant)
    res_evt = db.execute(sa.text("DELETE FROM events WHERE id = :e AND client_id = :c"), params)

    db.commit()

    return {
        "deleted": bool(res_evt.rowcount),
        "cascade": force,
        "counts": {
            "attendances": int(res_att.rowcount or 0),
            "certificates": int(res_cert.rowcount or 0),
            "enrollments": int(res_enr.rowcount or 0),
            "day_events": int(res_days.rowcount or 0),
            "events": int(res_evt.rowcount or 0),
        },
    }

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
