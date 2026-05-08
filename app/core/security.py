from datetime import datetime, timedelta
from typing import Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

# 1. Cấu hình bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 2. Xử lý Mật khẩu (Đã gộp và sửa lỗi 72 bytes)
def hash_password(password: str) -> str:
    if not password:
        return ""
    # Giới hạn 72 ký tự để không bao giờ bị lỗi Bcrypt
    password_str = str(password)[:72]
    return pwd_context.hash(password_str)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    return pwd_context.verify(plain_password, hashed_password)

# 3. Xử lý JWT Token
def _create_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + expires_delta
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_access_token(data: dict[str, Any]) -> str:
    return _create_token(
        {**data, "type": "access"},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

def create_refresh_token(data: dict[str, Any]) -> str:
    return _create_token(
        {**data, "type": "refresh"},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )

def decode_token(token: str) -> dict[str, Any]:
    """Decode JWT and return payload. Raises JWTError if invalid."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])