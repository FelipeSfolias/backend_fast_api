from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from app.api.v1.router import api_router
from app.core.logging import setup_logging
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request
from app.db.session import engine, SessionLocal
from app.db.base import Base

from app.db.bootstrap import run_migrations_and_seed  # <- AQUI (não de init_db)
from app.api.v1.router import api_router


api = FastAPI(title="Eventos API", version="1.0.0")
api.include_router(api_router, prefix="/api/v1")

@api.get("/healthz")
def healthz():
    return {"status": "ok"}

@api.on_event("startup")
def on_startup():
    run_migrations_and_seed()
                 # roda seed

setup_logging()

api = FastAPI(
    title="Controle de Eventos Acadêmicos - Backend (Grupo 1)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_parameters={"displayRequestDuration": True, "persistAuthorization": True},
)

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ajuste para domínios específicos em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# métricas /metrics (Prometheus)
Instrumentator().instrument(api).expose(api, include_in_schema=False, should_gzip=True)

api.include_router(api_router, prefix="/api/v1")

@api.get("/healthz", tags=["health"])
def healthz():
    return {"status": "ok"}

@api.on_event("startup")
def startup():
    run_migrations_and_seed()
@api.exception_handler(IntegrityError)
def handle_integrity_error(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={"code":"UNIQUE_VIOLATION","message":"Registro duplicado.","details":str(getattr(exc, "orig", exc))}
    )

@api.exception_handler(Exception)
def handle_unexpected(request: Request, exc: Exception):
    
    
    # log já sai no console; aqui padronizamos saída
    return JSONResponse(
        status_code=500,
        content={"code":"INTERNAL_ERROR","message":"Erro interno.","details":str(exc)}
    )