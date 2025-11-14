# app/db/base.py
from app.db.base_class import Base  # mantém

# Carrega módulos para registrar tabelas no metadata:
import app.models.client        # noqa: F401
import app.models.role          # noqa: F401
import app.models.user          # noqa: F401
import app.models.user_role     # noqa: F401  
import app.models.student       # noqa: F401
import app.models.event         # noqa: F401
import app.models.enrollment    # noqa: F401
import app.models.attendance    # noqa: F401
import app.models.certificate   # noqa: F401
try:
    import app.models.tokens    # noqa: F401  # se existir (RefreshToken)
except Exception:
    pass


__all__: list[str] = []