from fastapi import APIRouter
from app.api.v1 import health, auth, students, events, enrollments, gate, attendance, certificates, clients

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/{tenant}/auth", tags=["auth"])  # << aqui!
api_router.include_router(students.router, prefix="/{tenant}/students", tags=["students"])
api_router.include_router(events.router, prefix="/{tenant}/events", tags=["events"])
api_router.include_router(enrollments.router, prefix="/{tenant}", tags=["enrollments"])
api_router.include_router(gate.router, prefix="/{tenant}/gate", tags=["gate"])
api_router.include_router(attendance.router, prefix="/{tenant}/attendance", tags=["attendance"])
api_router.include_router(certificates.router, prefix="/{tenant}/certificates", tags=["certificates"])
api_router.include_router(clients.router, prefix="/{tenant}/client", tags=["client"])
# onde agrega os routers (ex.: app/api/router.py ou app/main.py)
api_router.include_router(clients.router, prefix="/{tenant}/client", tags=["client"])
api_router.include_router(clients.router, prefix="/client", tags=["client-debug"])  # apenas para /_debug/tenants
api_router.include_router(auth.router,       prefix="/{tenant}/auth", tags=["auth"])
api_router.include_router(students.router,   prefix="/{tenant}/students", tags=["students"])
api_router.include_router(events.router,     prefix="/{tenant}/events", tags=["events"])
api_router.include_router(enrollments.router,prefix="/{tenant}", tags=["enrollments"])   # <- AQUI
api_router.include_router(attendance.router, prefix="/{tenant}/attendance", tags=["attendance"])
api_router.include_router(certificates.router,prefix="/{tenant}/certificates", tags=["certificates"])
api_router.include_router(clients.router,    prefix="/{tenant}/client", tags=["client"])
api_router.include_router(health.router,     tags=["health"])