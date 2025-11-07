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
    clients,   # <- usa tenants/public routers definidos em clients.py
)

api_router = APIRouter()

# ---- rotas sem tenant ----
api_router.include_router(health.router, tags=["health"])

# ---- rotas com tenant no path ----
api_router.include_router(auth.router,         prefix="/{tenant}/auth",         tags=["auth"])
api_router.include_router(students.router,     prefix="/{tenant}/students",     tags=["students"])
api_router.include_router(events.router,       prefix="/{tenant}/events",       tags=["events"])

# ATENÇÃO: mantenho o padrão original do seu projeto:
# o router de enrollments já define /enrollments internamente,
# por isso o prefixo aqui é só "/{tenant}" (NÃO "/{tenant}/enrollments")
api_router.include_router(enrollments.router,  prefix="/{tenant}",              tags=["enrollments"])

api_router.include_router(gate.router,         prefix="/{tenant}/gate",         tags=["gate"])
api_router.include_router(attendance.router,   prefix="/{tenant}/attendance",   tags=["attendance"])
api_router.include_router(certificates.router, prefix="/{tenant}/certificates", tags=["certificates"])

# clients (escopo de tenant)
api_router.include_router(clients.tenant_router, prefix="/{tenant}/client",  tags=["client"])
# alias opcional em plural
api_router.include_router(clients.tenant_router, prefix="/{tenant}/clients", tags=["client"])

# ---- rotas públicas (sem tenant) para provisionar client ----
api_router.include_router(clients.public_router, prefix="/client",  tags=["client"])
# alias opcional em plural
api_router.include_router(clients.public_router, prefix="/clients", tags=["client"])
