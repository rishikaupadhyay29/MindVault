import time

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Conversation, Note, NoteChunk, ProcessingStatus, User
from app.security import current_user
from app.services import embedding, ollama
from app.services.graph import graph_edges

router = APIRouter(prefix="/api", tags=["stats"])
STARTED = time.time()


@router.get("/stats")
def stats(user: User = Depends(current_user), db: Session = Depends(get_db)):
    mine = Note.owner_id == user.id
    count = lambda *w: db.scalar(select(func.count()).select_from(Note).where(mine, *w)) or 0
    chunks = db.scalar(select(func.count()).select_from(NoteChunk).join(Note, Note.id == NoteChunk.note_id).where(mine)) or 0
    edges = graph_edges(db, user.id, 0.5)
    titles = {n.id: n.title for n in db.scalars(select(Note).where(mine))}
    recent = db.scalars(select(Note).where(mine).order_by(Note.updated_at.desc()).limit(6)).all()
    convs = db.scalars(select(Conversation).where(Conversation.owner_id == user.id)
                       .order_by(Conversation.updated_at.desc()).limit(5)).all()
    activity = [dict(type="note_created" if n.created_at == n.updated_at else "note_updated", id=str(n.id),
                     title=n.title, at=n.updated_at.isoformat()) for n in recent]
    activity += [dict(type="conversation", id=str(c.id), title=c.title, at=c.updated_at.isoformat()) for c in convs]
    activity.sort(key=lambda a: a["at"], reverse=True)
    return {
        "notes": count(), "indexed": count(Note.processing_status == ProcessingStatus.indexed),
        "processing": count(Note.processing_status.in_([ProcessingStatus.pending, ProcessingStatus.processing])),
        "failed": count(Note.processing_status == ProcessingStatus.failed), "documents": count(Note.source_type == "document"),
        "chunks": chunks, "connections": len(edges), "conversations": db.scalar(
            select(func.count()).select_from(Conversation).where(Conversation.owner_id == user.id)) or 0,
        "recent": [dict(id=str(n.id), title=n.title, preview=n.content[:200], tags=n.tags, status=n.processing_status.value,
                        updated_at=n.updated_at.isoformat()) for n in recent],
        "activity": activity[:8],
        "discoveries": [dict(a=str(a), b=str(b), a_title=titles.get(a, ""), b_title=titles.get(b, ""), score=round(s, 3))
                        for a, b, s in edges[:3]],
        "suggestions": [f"What do my notes say about {n.title}?" for n in recent if n.processing_status == ProcessingStatus.indexed][:3],
    }


@router.get("/diagnostics")
async def diagnostics(user: User = Depends(current_user), db: Session = Depends(get_db)):
    pg: dict = {}
    try:
        t0 = time.perf_counter()
        pg = {"status": "ok", "version": db.scalar(text("SHOW server_version")),
              "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
        ext = db.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
        vec = {"status": "ok" if ext else "missing", "version": ext}
        if ext:
            vec["indexes"] = [r[0] for r in db.execute(text(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'note_chunks' AND indexdef ILIKE '%hnsw%'"))]
    except Exception as e:
        pg, vec = {"status": "error", "detail": str(e)[:200]}, {"status": "unknown"}
    emb = embedding.get_embedder()
    by_status = dict(db.execute(select(Note.processing_status, func.count()).where(Note.owner_id == user.id)
                                .group_by(Note.processing_status)).all())
    failures = db.scalars(select(Note).where(Note.owner_id == user.id, Note.processing_status == ProcessingStatus.failed)
                          .order_by(Note.updated_at.desc()).limit(10)).all()
    return {
        "api": {"status": "ok", "uptime_s": int(time.time() - STARTED), "environment": settings.environment},
        "postgres": pg, "pgvector": vec, "ollama": await ollama.get_ollama().status(),
        "embedding": {"model": settings.embedding_model, "dimensions": settings.embedding_dim,
                      "loaded": getattr(emb, "_model", None) is not None},
        "redis": {"status": "not_used", "detail": "Background jobs run in-process; Redis is not required."},
        "processing": {"by_status": {k.value: v for k, v in by_status.items()},
                       "errors": [dict(id=str(n.id), title=n.title, error=n.processing_error) for n in failures]},
    }
