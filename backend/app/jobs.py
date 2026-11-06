"""Note processing job. This module owns its transactions (commit/rollback)."""
import logging
import time
import uuid

from sqlalchemy import select

from app import db
from app.config import settings
from app.models import Note, ProcessingStatus
from app.services import embedding
from app.services.chunking import chunk_text
from app.services.indexing import clear_chunks, replace_chunks

log = logging.getLogger(__name__)


def _mark_failed(note_id: uuid.UUID, content_hash: str, message: str) -> None:
    with db.SessionLocal() as s:
        try:
            note = s.get(Note, note_id, with_for_update=True)
            if note is None or note.content_hash != content_hash:
                return
            clear_chunks(s, note)  # never leave chunks that no longer match the note
            note.processing_status = ProcessingStatus.failed
            note.processing_error = message[:500]
            note.indexed_hash = None
            s.commit()
        except Exception:
            s.rollback()
            log.exception("could not record processing failure for %s", note_id)


def process_note(note_id: uuid.UUID) -> None:
    # 1) claim the note, committing 'processing' so the UI can show it
    with db.SessionLocal() as s:
        note = s.get(Note, note_id, with_for_update=True)
        if note is None:
            return
        if note.processing_status == ProcessingStatus.indexed and note.indexed_hash == note.content_hash:
            return  # duplicate request, nothing to do
        text, content_hash = note.content, note.content_hash
        note.processing_status = ProcessingStatus.processing
        note.processing_error = None
        s.commit()

    # 2) chunk + embed outside any DB transaction (slow, CPU bound)
    chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
    vectors, error = [], None
    for attempt in range(settings.embed_retries + 1):  # transient failures (memory pressure, model warm-up) get retried
        try:
            vectors = embedding.get_embedder().embed([c.content for c in chunks]) if chunks else []
            error = None
            break
        except Exception as e:
            error = e
            log.warning("embedding attempt %s failed for note %s: %s", attempt + 1, note_id, e)
            if attempt < settings.embed_retries:
                time.sleep(settings.embed_retry_delay * (attempt + 1))
    if error is not None:
        log.error("embedding failed for note %s", note_id)
        _mark_failed(note_id, content_hash, str(error))
        return

    # 3) store atomically; 'indexed' is only committed together with the chunks
    with db.SessionLocal() as s:
        try:
            note = s.get(Note, note_id, with_for_update=True)
            if note is None or note.content_hash != content_hash:
                return  # deleted or edited meanwhile; the newer job owns the result
            replace_chunks(s, note, chunks, vectors)
            note.processing_status = ProcessingStatus.indexed
            note.indexed_hash = content_hash
            note.processing_error = None
            s.commit()
        except Exception as e:
            s.rollback()
            log.exception("storing chunks failed for note %s", note_id)
            _mark_failed(note_id, content_hash, f"Could not store index: {e}")


def recover_stuck() -> list[uuid.UUID]:
    """After a crash/restart, notes left pending/processing would never finish. Re-queue them."""
    with db.SessionLocal() as s:
        notes = s.scalars(select(Note).where(
            Note.processing_status.in_([ProcessingStatus.pending, ProcessingStatus.processing]))).all()
        for n in notes:
            n.processing_status = ProcessingStatus.pending
        ids = [n.id for n in notes]
        s.commit()
    return ids
