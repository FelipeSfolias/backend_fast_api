from typing import TypeVar, Generic, Type, Any, Optional, List, Dict
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchema = TypeVar("CreateSchema", bound=BaseModel)
UpdateSchema = TypeVar("UpdateSchema", bound=BaseModel)

class CRUDBase(Generic[ModelType, CreateSchema, UpdateSchema]):
    def __init__(self, model: Type[ModelType]): self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        return db.get(self.model, id)

    def get_multi(self, db: Session, skip=0, limit=100) -> List[ModelType]:
        return db.query(self.model).offset(skip).limit(limit).all()

    def create(self, db: Session, obj_in: CreateSchema, extra: Dict[str, Any] | None=None) -> ModelType:
        data = obj_in.model_dump()
        if extra: data.update(extra)
        obj = self.model(**data)
        db.add(obj); db.commit(); db.refresh(obj)
        return obj

    def update(self, db: Session, db_obj: ModelType, obj_in: UpdateSchema | Dict[str, Any]) -> ModelType:
        data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        for f,v in data.items(): setattr(db_obj, f, v)
        db.add(db_obj); db.commit(); db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, id: Any) -> Optional[ModelType]:
        obj = self.get(db, id)
        if not obj: return None
        db.delete(obj); db.commit(); return obj
