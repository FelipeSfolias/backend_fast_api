# app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1 import (
<<<<<<< HEAD
    health,
    auth,
    students,
    events,
    enrollments,
    gate,
    attendance,
    certificates,
    clients,
    users,
=======
    health, auth, students, events, enrollments, gate, attendance, certificates, clients
>>>>>>> a4563aeb7b1c48000b196e1b282b41fdb48d1fc0
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
<<<<<<< HEAD
api_router.include_router(clients.router,      prefix="/{tenant}/client",       tags=["client"])
api_router.include_router(users.router, prefix="/{tenant}/users", tags=["users"])
# debug opcional para listar tenants sem escopo
api_router.include_router(clients.router,      prefix="/client",                tags=["client-debug"])
=======

# Clients — escolha **um** prefixo. Recomendo singular.
api_router.include_router(clients.tenant_router, prefix="/{tenant}/client", tags=["client"])

# Provisionamento sem tenant
api_router.include_router(clients.public_router, prefix="/client", tags=["client"])
>>>>>>> a4563aeb7b1c48000b196e1b282b41fdb48d1fc0
