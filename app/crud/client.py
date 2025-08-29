from app.crud.base import CRUDBase
from app.models.client import Client
from app.schemas.client import ClientCreate, Client as ClientOut
client_crud = CRUDBase[Client, ClientCreate, ClientOut](Client)
