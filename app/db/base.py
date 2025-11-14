# app/db/base.py
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData

naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=naming_convention)

# 🔴 IMPORTE TODOS OS MODELS AQUI
from app.models.client import Client
from app.models.user import User
from app.models.user_role import user_roles
from app.models.role import Role
from app.models.student import Student
from app.models.event import Event
from app.models.day_event import DayEvent
from app.models.enrollment import Enrollment
from app.models.attendance import Attendance
from app.models.certificate import Certificate
from app.models.audit import AuditLog
from app.models.tokens import RefreshToken
