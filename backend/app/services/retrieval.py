import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Note, NoteChunk, ProcessingStatus
from app.services import embedding


def embed_query(text: str) -> list[float]:
    return embedding.get_embedder().embed([text])[0]


def retrieve_chunks(db: Session, user_id: uuid.UUID, vec: list[float], limit: int) -> list[dict]:
    """Nearest chunks by cosine distance, only from this user's fully indexed notes."""
    dist = NoteChunk.embedding.cosine_distance(vec).label("dist")
    rows = db.execute(
        select(NoteChunk.note_id, NoteChunk.chunk_index, NoteChunk.content, Note.title, Note.tags, Note.source_type, dist)
        .join(Note, Note.id == NoteChunk.note_id)
        .where(Note.owner_id == user_id, Note.processing_status == ProcessingStatus.indexed,
               Note.indexed_hash == Note.content_hash)
        .order_by(dist).limit(limit)).all()
    return [dict(note_id=r.note_id, chunk_index=r.chunk_index, content=r.content, title=r.title, tags=r.tags,
                 source_type=r.source_type, score=1.0 - float(r.dist)) for r in rows]


def search_notes(db: Session, user_id: uuid.UUID, query: str, limit: int, min_score: float) -> list[dict]:
    """Best chunk per note, ranked by cosine similarity (a ranking signal, not a probability)."""
    hits = retrieve_chunks(db, user_id, embed_query(query), min(limit * 6, 120))
    best: dict[uuid.UUID, dict] = {}
    for h in hits:
        if h["score"] >= min_score and h["note_id"] not in best:
            best[h["note_id"]] = h
    return sorted(best.values(), key=lambda h: -h["score"])[:limit]
