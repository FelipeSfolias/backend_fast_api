# migrations/env.py
import os
from alembic import context
from sqlalchemy import engine_from_config, pool
from app.db.base import Base

# (1) carregar .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# (2) normalizar URL
def _normalize(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

config = context.config

db_url = os.getenv("DATABASE_URL")
if not db_url or db_url.strip() == "":
    db_url = "sqlite:///./data/events.db"  # fallback
db_url = _normalize(db_url)

# (3) Alembic usará esta URL
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
