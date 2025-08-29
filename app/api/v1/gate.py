from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_db, get_tenant, get_current_user_scoped
from app.core.rbac import require_roles
from app.services.qr import validate_qr_token
from app.crud.attendance import attendance_crud
from app.models.enrollment import Enrollment
from app.models.day_event import DayEvent

router = APIRouter()

@router.post("/scan", dependencies=[Depends(require_roles("gate","organizer","admin"))])
def scan(payload: dict, db: Session = Depends(get_db), tenant=Depends(get_tenant), _=Depends(get_current_user_scoped)):
    # payload: {enrollment_id | qr_token, day_event_id, action: checkin|checkout}
    enr: Enrollment | None = None
    if "enrollment_id" in payload:
        enr = db.get(Enrollment, int(payload["enrollment_id"]))
    elif "qr_token" in payload:
        # find by token among enrollments of the event day
        day = db.get(DayEvent, int(payload["day_event_id"]))
        if not day: raise HTTPException(404, "DAY_NOT_FOUND")
        # candidato: validar token contra seed
        # (em produção, use um índice/estrutura para lookup eficiente)
        q = db.execute(select(Enrollment).join(Enrollment.event).where(Enrollment.event_id==day.event_id)).scalars().all()
        for e in q:
            if validate_qr_token(e.qr_seed, payload["qr_token"]): enr = e; break
    if not enr or enr.event.client_id != tenant.id:
        raise HTTPException(404, detail="ENROLLMENT_NOT_FOUND")

    action = payload.get("action","checkin")
    try:
        if action == "checkin":
            att = attendance_crud.checkin(db, enrollment_id=enr.id, day_event_id=int(payload["day_event_id"]))
        else:
            att = attendance_crud.checkout(db, enrollment_id=enr.id, day_event_id=int(payload["day_event_id"]))
    except RuntimeError as ex:
        if str(ex) == "ALREADY_CHECKED_IN":
            raise HTTPException(status_code=409, detail={"code":"ALREADY_CHECKED_IN"})
        raise
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=str(ex))

    return {"attendance_id": att.id, "checkin_at": att.checkin_at, "checkout_at": att.checkout_at}
