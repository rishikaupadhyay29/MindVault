import uuid

import pytest
from sqlalchemy import delete, text

from app import db, jobs
from app.models import Note, NoteChunk, ProcessingStatus
from app.services import embedding
from app.services.embedding import EmbeddingError
from tests.conftest import chunk_rows

LONG = "\n\n".join(f"Paragraph {i}: PostgreSQL indexes reduce the data scanned by a query. " * 6 for i in range(8))


def create(client, content, title="T"):
    r = client.post("/api/notes", json={"title": title, "content": content})
    assert r.status_code == 201
    return r.json()


def get(client, nid):
    return client.get(f"/api/notes/{nid}").json()


def test_create_generates_chunks_and_384d_embeddings(client, embedder):
    created = create(client, LONG)
    assert created["processing_status"] == "pending"  # never 'indexed' before storage
    note = get(client, created["id"])
    rows = chunk_rows(note["id"])
    assert note["processing_status"] == "indexed" and len(rows) > 1
    assert note["chunk_count"] == len(rows)
    assert {r.dims for r in rows} == {384}
    assert note["content"] == LONG  # original preserved


def test_update_replaces_old_chunks(client, embedder):
    nid = create(client, LONG)["id"]
    old = {r.id for r in chunk_rows(nid)}
    client.put(f"/api/notes/{nid}", json={"content": "Redis is an in-memory cache used for fast lookups."})
    rows = chunk_rows(nid)
    assert get(client, nid)["processing_status"] == "indexed"
    assert len(rows) == 1 and "Redis" in rows[0].content
    assert not old & {r.id for r in rows}


def test_clearing_content_removes_chunks(client, embedder):
    nid = create(client, LONG)["id"]
    client.put(f"/api/notes/{nid}", json={"content": "   "})
    note = get(client, nid)
    assert chunk_rows(nid) == [] and note["chunk_count"] == 0 and note["processing_status"] == "indexed"


def test_title_only_update_does_not_reprocess(client, embedder):
    nid = create(client, LONG)["id"]
    before = [r.id for r in chunk_rows(nid)]
    client.put(f"/api/notes/{nid}", json={"title": "New title"})
    assert [r.id for r in chunk_rows(nid)] == before


def test_delete_removes_chunks(client, embedder):
    nid = create(client, LONG)["id"]
    assert chunk_rows(nid)
    assert client.delete(f"/api/notes/{nid}").status_code == 204
    assert chunk_rows(nid) == [] and client.get(f"/api/notes/{nid}").status_code == 404


def test_embedding_failure_marks_failed_and_retry_recovers(client, monkeypatch):
    class Broken:
        def embed(self, texts):
            raise EmbeddingError("model exploded")

    monkeypatch.setattr(embedding, "get_embedder", lambda: Broken())
    nid = create(client, LONG)["id"]
    note = get(client, nid)
    assert note["processing_status"] == "failed" and "exploded" in note["processing_error"]
    assert chunk_rows(nid) == [] and note["content"] == LONG  # note itself is safe
    monkeypatch.setattr(embedding, "get_embedder", lambda: __import__("tests.conftest", fromlist=["x"]).FakeEmbedder())
    client.post(f"/api/notes/{nid}/reprocess")
    assert get(client, nid)["processing_status"] == "indexed" and chunk_rows(nid)


def test_failed_update_leaves_other_notes_intact(client, embedder, monkeypatch):
    a = create(client, LONG, "A")["id"]
    b = create(client, "Short note about Docker.", "B")["id"]
    keep = [r.id for r in chunk_rows(a)]

    class Broken:
        def embed(self, texts):
            raise EmbeddingError("nope")

    monkeypatch.setattr(embedding, "get_embedder", lambda: Broken())
    client.put(f"/api/notes/{b}", json={"content": "Changed text that will fail."})
    assert get(client, b)["processing_status"] == "failed"
    assert [r.id for r in chunk_rows(a)] == keep and get(client, a)["processing_status"] == "indexed"


def test_store_failure_rolls_back(client, embedder, monkeypatch):
    def boom(session, note, chunks, vectors):
        session.execute(delete(NoteChunk).where(NoteChunk.note_id == note.id))
        raise RuntimeError("disk full")

    monkeypatch.setattr(jobs, "replace_chunks", boom)
    nid = create(client, LONG)["id"]
    note = get(client, nid)
    assert note["processing_status"] == "failed" and "disk full" in note["processing_error"]
    assert note["chunk_count"] == len(chunk_rows(nid)) == 0


def test_stale_job_does_not_overwrite_newer_edit(client, monkeypatch):
    nid = create(client, "placeholder", "S")["id"]  # indexed via real flow below, so reset first
    with db.SessionLocal() as s:
        n = s.get(Note, uuid.UUID(nid))
        n.processing_status, n.indexed_hash = ProcessingStatus.pending, None
        s.execute(delete(NoteChunk))
        s.commit()

    class EditsDuringEmbed:
        def embed(self, texts):
            with db.SessionLocal() as s:  # simulate a concurrent user edit
                n = s.get(Note, uuid.UUID(nid))
                n.content, n.content_hash = "edited meanwhile", "different-hash"
                s.commit()
            return [[0.1] * 384 for _ in texts]

    monkeypatch.setattr(embedding, "get_embedder", lambda: EditsDuringEmbed())
    jobs.process_note(uuid.UUID(nid))
    assert chunk_rows(nid) == []
    with db.SessionLocal() as s:
        assert s.get(Note, uuid.UUID(nid)).processing_status != ProcessingStatus.indexed


def test_duplicate_processing_is_noop(client, embedder):
    nid = create(client, LONG)["id"]
    ids = [r.id for r in chunk_rows(nid)]
    jobs.process_note(uuid.UUID(nid))
    assert [r.id for r in chunk_rows(nid)] == ids
