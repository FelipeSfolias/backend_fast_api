from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
from app.models.certificate import Certificate, CertificateStatus
from app.models.enrollment import Enrollment
from app.models.event import Event
from app.models.day_event import DayEvent
from app.models.attendance import Attendance
from app.models.client import Client
from app.services.certificates import render_certificate_pdf, build_verify_code

def issue_if_eligible(db: Session, *, enrollment_id: int) -> Certificate | None:
    enr = db.get(Enrollment, enrollment_id)
    event = db.get(Event, enr.event_id)
    client = db.get(Client, event.client_id)

    days = db.query(DayEvent).filter(DayEvent.event_id==event.id).all()
    present_days = db.query(Attendance).filter(
        Attendance.enrollment_id==enrollment_id,
        Attendance.checkin_at.isnot(None)
    ).count()
    total_days = len(days) or 1
    pct = (present_days/total_days)*100

    min_pct = event.min_presence_pct or client.default_min_presence_pct or 75
    if pct < min_pct:
        return None

    code = build_verify_code(enrollment_id)
    pdf_url = render_certificate_pdf(
        enrollment_id=enrollment_id, event=event, student=enr.student, client=client, verify_code=code
    )
    cert = Certificate(enrollment_id=enrollment_id, issued_at=datetime.utcnow(),
                       pdf_url=pdf_url, verify_code=code, status=CertificateStatus.issued)
    db.add(cert); db.commit(); db.refresh(cert)
    return cert
