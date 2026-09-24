import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from gateway.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def generate_api_key() -> tuple[str, str, str]:
    """Returns (raw_key, key_hash, key_prefix). The raw key is shown to the
    caller exactly once - only the hash and prefix are persisted."""
    raw = f"sk-proj-{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(raw)
    return raw, key_hash, raw[:12]


def hash_api_key(raw_key: str) -> str:
    # SHA-256, not bcrypt: the key itself is already high-entropy, and the data
    # plane needs to verify it on every request - bcrypt's deliberate slowness
    # is the wrong tradeoff here (it's for low-entropy human passwords).
    return hashlib.sha256(raw_key.encode()).hexdigest()
