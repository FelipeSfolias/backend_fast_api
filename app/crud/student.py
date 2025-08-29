from app.crud.base import CRUDBase
from app.models.student import Student
from app.schemas.student import StudentCreate, StudentUpdate
student_crud = CRUDBase[Student, StudentCreate, StudentUpdate](Student)
