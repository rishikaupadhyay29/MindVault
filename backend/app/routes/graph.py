from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import current_user
from app.services.graph import build_graph

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph")
def graph(threshold: float = Query(0.45, ge=0.1, le=0.95), user: User = Depends(current_user), db: Session = Depends(get_db)):
    return build_graph(db, user.id, threshold)
