import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Note, User
from app.security import DUMMY_HASH, create_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
_fails: dict[str, list[float]] = {}


class Credentials(BaseModel):
    email: str = Field(pattern=EMAIL, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class RegisterIn(Credentials):
    display_name: str = Field("", max_length=80)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    display_name: str
    prefs: dict


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProfileIn(BaseModel):
    display_name: str | None = Field(None, max_length=80)
    prefs: dict | None = None


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


def _check_rate(key: str) -> None:
    now = time.time()
    recent = [t for t in _fails.get(key, []) if now - t < 900]
    _fails[key] = recent
    if len(recent) >= 5:
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if not settings.allow_registration:
        raise HTTPException(403, "Registration is disabled.")
    email = body.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists.")
    first = db.scalar(select(func.count()).select_from(User)) == 0
    user = User(email=email, password_hash=hash_password(body.password),
                display_name=body.display_name.strip() or email.split("@")[0], prefs={})
    db.add(user)
    db.flush()
    if first:  # notes created before accounts existed belong to the first account
        db.execute(update(Note).where(Note.owner_id.is_(None)).values(owner_id=user.id))
    db.commit()
    return TokenOut(access_token=create_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(body: Credentials, request: Request, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    key = f"{request.client.host if request.client else '?'}:{email}"
    _check_rate(key)
    user = db.scalar(select(User).where(User.email == email))
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not ok:
        _fails.setdefault(key, []).append(time.time())
        raise HTTPException(401, "Incorrect email or password.")
    _fails.pop(key, None)
    return TokenOut(access_token=create_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.display_name is not None:
        user.display_name = body.display_name.strip() or user.display_name
    if body.prefs is not None:
        if len(json.dumps(body.prefs)) > 4000:
            raise HTTPException(422, "Preferences are too large.")
        user.prefs = body.prefs
    db.commit()
    return user


@router.post("/password", status_code=204)
def change_password(body: PasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect.")
    user.password_hash = hash_password(body.new_password)
    db.commit()
