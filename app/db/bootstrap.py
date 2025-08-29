# app/db/bootstrap.py
import os
from alembic import command
from alembic.config import Config

from app.db.session import SessionLocal
from app.db.init_db import init_db

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def run_migrations_and_seed() -> None:
    # Aponta explicitamente para alembic.ini e migrations/
    cfg = Config(os.path.join(BASE_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BASE_DIR, "migrations"))

    # Aplica todas as migrações
    command.upgrade(cfg, "head")

    # Roda o seed
    with SessionLocal() as db:
        init_db(db)
