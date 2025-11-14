# app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1 import (
    health,
    auth,
    students,
    events,
    enrollments,
    gate,
    attendance,
    certificates,
    clients,
    # users,  # descomente esta linha e o include lá embaixo somente se você já criou app/api/v1/users.py
)

api_router = APIRouter()

# -------- rotas sem tenant --------
api_router.include_router(health.router, tags=["health"])
# POST /api/v1/client (criação de cliente) + /api/v1/client/_debug/tenants
api_router.include_router(clients.router, prefix="/client", tags=["client-public"])

# -------- rotas com tenant --------
api_router.include_router(auth.router,         prefix="/{tenant}/auth",         tags=["auth"])
api_router.include_router(students.router,     prefix="/{tenant}/students",     tags=["students"])
api_router.include_router(events.router,       prefix="/{tenant}/events",       tags=["events"])
api_router.include_router(enrollments.router,  prefix="/{tenant}",              tags=["enrollments"])
api_router.include_router(gate.router,         prefix="/{tenant}/gate",         tags=["gate"])
api_router.include_router(attendance.router,   prefix="/{tenant}/attendance",   tags=["attendance"])
api_router.include_router(certificates.router, prefix="/{tenant}/certificates", tags=["certificates"])
# GET/PUT do client do próprio tenant: /api/v1/{tenant}/client[/...]
api_router.include_router(clients.router,      prefix="/{tenant}/client",       tags=["client"])
# api_router.include_router(users.router,        prefix="/{tenant}/users",        tags=["users"])  # só se existir
