from app.crud.base import CRUDBase
from app.models.day_event import DayEvent as DayEventModel
from app.schemas.day_event import DayEventCreate, DayEvent as DayEventSchema

day_event_crud = CRUDBase[DayEventModel, DayEventCreate, DayEventSchema](DayEventModel)