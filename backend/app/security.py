import base64
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User

_bearer = HTTPBearer(auto_error=False)
_b64 = lambda b: base64.b64encode(b).decode()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${_b64(salt)}${_b64(h)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(got, base64.b64decode(h))
    except Exception:
        return False


DUMMY_HASH = hash_password("dummy-password-for-timing")


def create_token(user_id: uuid.UUID) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.secret_key, algorithm="HS256")


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)) -> User:
    err = HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise err
    try:
        uid = uuid.UUID(jwt.decode(creds.credentials, settings.secret_key, algorithms=["HS256"])["sub"])
    except Exception:
        raise err
    user = db.get(User, uid)
    if user is None:
        raise err
    return user
