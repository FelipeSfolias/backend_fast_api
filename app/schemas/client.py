from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any

class ClientBase(BaseModel):
    name: str
    cnpj: str
    slug: str
    logo_url: Optional[str] = None

    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    certificate_template_html: Optional[str] = None
    default_min_presence_pct: Optional[int] = None
    lgpd_policy_text: Optional[str] = None

    config_json: Dict[str, Any] = {}

class ClientCreate(ClientBase):  # usado por seed/superadmin
    pass

class ClientUpdate(BaseModel):   # edição parcial
    name: str | None = None
    cnpj: str | None = None
    logo_url: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    certificate_template_html: str | None = None
    default_min_presence_pct: int | None = None
    lgpd_policy_text: str | None = None
    config_json: Dict[str, Any] | None = None

class Client(ClientBase):
    id: int
