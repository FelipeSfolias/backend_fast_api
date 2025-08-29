from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from hashlib import sha256
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.tokens import IdempotencyKey

class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in {"POST","PUT","PATCH","DELETE"}:
            return await call_next(request)

        key = request.headers.get("Idempotency-Key")
        if not key:
            return await call_next(request)

        signature = sha256((request.method + request.url.path).encode()).hexdigest()
        with SessionLocal() as db:
            exists = db.execute(select(IdempotencyKey).where(IdempotencyKey.key==key, IdempotencyKey.signature==signature)).scalar_one_or_none()
            if exists:
                return Response(content=exists.response_body, media_type=exists.response_mime, status_code=exists.status_code)

        response = await call_next(request)
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        with SessionLocal() as db:
            db.add(IdempotencyKey(key=key, signature=signature, response_body=body, response_mime=response.media_type or "application/json", status_code=response.status_code))
            db.commit()
        return Response(content=body, media_type=response.media_type, status_code=response.status_code)
