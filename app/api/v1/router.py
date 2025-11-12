# app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1 import (
    health, auth, students, events, enrollments, gate, attendance, certificates, clients
)

api_router = APIRouter()

# Sem tenant
api_router.include_router(health.router, tags=["health"])

# Com tenant
api_router.include_router(auth.router,         prefix="/{tenant}/auth",         tags=["auth"])
api_router.include_router(students.router,     prefix="/{tenant}/students",     tags=["students"])
api_router.include_router(events.router,       prefix="/{tenant}/events",       tags=["events"])
api_router.include_router(enrollments.router,  prefix="/{tenant}",              tags=["enrollments"])
api_router.include_router(gate.router,         prefix="/{tenant}/gate",         tags=["gate"])
api_router.include_router(attendance.router,   prefix="/{tenant}/attendance",   tags=["attendance"])
api_router.include_router(certificates.router, prefix="/{tenant}/certificates", tags=["certificates"])

# Clients — escolha **um** prefixo. Recomendo singular.
api_router.include_router(clients.tenant_router, prefix="/{tenant}/client", tags=["client"])

# Provisionamento sem tenant
api_router.include_router(clients.public_router, prefix="/client", tags=["client"])
