import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Note, ProcessingStatus

_OK = "n.owner_id = :u AND n.processing_status = 'indexed' AND n.indexed_hash = n.content_hash"

# For each chunk, ask the index for its k nearest chunks in OTHER notes (no all-pairs scan),
# then aggregate to note level: edge score = best chunk-to-chunk cosine similarity.
_EDGES = text(f"""
SELECT LEAST(s, d) AS a, GREATEST(s, d) AS b, MAX(score) AS score FROM (
  SELECT a.note_id AS s, b.note_id AS d, 1 - b.dist AS score
  FROM (SELECT c.note_id, c.embedding FROM note_chunks c JOIN notes n ON n.id = c.note_id
        WHERE {_OK} ORDER BY c.created_at DESC LIMIT :maxchunks) a
  CROSS JOIN LATERAL (
    SELECT c.note_id, c.embedding <=> a.embedding AS dist
    FROM note_chunks c JOIN notes n ON n.id = c.note_id
    WHERE {_OK} AND c.note_id <> a.note_id
    ORDER BY c.embedding <=> a.embedding LIMIT :k) b
) p GROUP BY 1, 2 HAVING MAX(score) >= :t ORDER BY score DESC LIMIT :maxedges
""")

_RELATED = text(f"""
SELECT b.note_id AS id, MAX(1 - b.dist) AS score
FROM note_chunks a
CROSS JOIN LATERAL (
  SELECT c.note_id, c.embedding <=> a.embedding AS dist
  FROM note_chunks c JOIN notes n ON n.id = c.note_id
  WHERE {_OK} AND c.note_id <> a.note_id
  ORDER BY c.embedding <=> a.embedding LIMIT :k) b
WHERE a.note_id = :nid
GROUP BY b.note_id HAVING MAX(1 - b.dist) >= :t ORDER BY score DESC LIMIT :limit
""")


def graph_edges(db: Session, user_id: uuid.UUID, threshold: float, k: int = 5,
                max_chunks: int = 1500, max_edges: int = 1000) -> list[tuple[uuid.UUID, uuid.UUID, float]]:
    rows = db.execute(_EDGES, dict(u=user_id, t=threshold, k=k, maxchunks=max_chunks, maxedges=max_edges)).all()
    return [(r.a, r.b, float(r.score)) for r in rows]


def build_graph(db: Session, user_id: uuid.UUID, threshold: float, limit_nodes: int = 300) -> dict:
    notes = db.scalars(select(Note).where(
        Note.owner_id == user_id, Note.processing_status == ProcessingStatus.indexed,
        Note.indexed_hash == Note.content_hash, Note.chunk_count > 0)
        .order_by(Note.updated_at.desc()).limit(limit_nodes)).all()
    ids = {n.id for n in notes}
    edges = [e for e in graph_edges(db, user_id, threshold) if e[0] in ids and e[1] in ids]
    deg: dict[uuid.UUID, int] = {}
    for a, b, _ in edges:
        deg[a] = deg.get(a, 0) + 1
        deg[b] = deg.get(b, 0) + 1
    return {
        "nodes": [dict(id=str(n.id), title=n.title, tags=n.tags, preview=n.content[:160], chunks=n.chunk_count,
                       degree=deg.get(n.id, 0)) for n in notes],
        "edges": [dict(source=str(a), target=str(b), score=round(s, 4)) for a, b, s in edges],
        "threshold": threshold,
    }


def related_notes(db: Session, user_id: uuid.UUID, note_id: uuid.UUID, threshold: float = 0.3, limit: int = 6) -> list[dict]:
    rows = db.execute(_RELATED, dict(u=user_id, nid=note_id, t=threshold, k=5, limit=limit)).all()
    titles = {n.id: n for n in db.scalars(select(Note).where(Note.id.in_([r.id for r in rows])))} if rows else {}
    return [dict(id=str(r.id), title=titles[r.id].title, tags=titles[r.id].tags, score=round(float(r.score), 4))
            for r in rows if r.id in titles]
