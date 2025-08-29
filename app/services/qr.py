import hmac, hashlib, time
from app.core.config import settings

def build_qr_token(qr_seed: str) -> str:
    # nonce rotativo por janela de N segundos
    window = int(time.time() // settings.QR_ROTATION_SECONDS)
    msg = f"{qr_seed}:{window}".encode()
    return hmac.new(key=qr_seed.encode(), msg=msg, digestmod=hashlib.sha256).hexdigest()[:32]

def validate_qr_token(qr_seed: str, token: str, skew_windows: int = 1) -> bool:
    # tolerância de clock skew: ±1 janela
    current = int(time.time() // settings.QR_ROTATION_SECONDS)
    for w in (current-1, current, current+1)[: 2*skew_windows+1]:
        msg = f"{qr_seed}:{w}".encode()
        expected = hmac.new(qr_seed.encode(), msg, hashlib.sha256).hexdigest()[:32]
        if hmac.compare_digest(expected, token):
            return True
    return False
