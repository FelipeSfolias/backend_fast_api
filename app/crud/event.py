from app.crud.base import CRUDBase
from app.models.event import Event
from app.schemas.event import EventCreate, EventUpdate
event_crud = CRUDBase[Event, EventCreate, EventUpdate](Event)
