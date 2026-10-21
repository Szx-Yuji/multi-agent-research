"""Password hashing and bearer-token auth."""
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import config
from db import User, get_session

_hasher = PasswordHasher()

# auto_error=False so anonymous requests fall through instead of 403-ing:
# research works signed out, history does not.
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
        return True
    except (VerifyMismatchError, VerificationError):
        return False


def create_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(seconds=config.AUTH_TOKEN_TTL_SECONDS),
        },
        config.AUTH_SECRET,
        algorithm="HS256",
    )


def decode_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, config.AUTH_SECRET, algorithms=["HS256"])
        return int(payload["sub"])
    except Exception:
        return None


def current_user_optional(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Optional[User]:
    if creds is None:
        return None
    user_id = decode_token(creds.credentials)
    if user_id is None:
        return None
    with get_session() as session:
        return session.get(User, user_id)


def current_user(user: Optional[User] = Depends(current_user_optional)) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
