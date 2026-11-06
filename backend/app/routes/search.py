from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import current_user
from app.services.embedding import EmbeddingError
from app.services.retrieval import search_notes

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
def search(q: str = Query(..., min_length=2, max_length=500), limit: int = Query(8, ge=1, le=25),
           min_score: float = Query(0.15, ge=0, le=1), user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        hits = search_notes(db, user.id, q.strip(), limit, min_score)
    except EmbeddingError as e:
        raise HTTPException(503, f"Search is unavailable right now: {e}")
    return {"query": q, "results": [dict(note_id=str(h["note_id"]), title=h["title"], tags=h["tags"],
                                         source_type=h["source_type"], score=round(h["score"], 4),
                                         excerpt=h["content"][:400], chunk_index=h["chunk_index"]) for h in hits]}
