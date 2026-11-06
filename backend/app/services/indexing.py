"""Chunk storage helpers. They never commit or roll back: the caller owns the transaction."""
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Note, NoteChunk
from app.services.chunking import Chunk


def replace_chunks(session: Session, note: Note, chunks: list[Chunk], vectors: list[list[float]]) -> None:
    session.execute(delete(NoteChunk).where(NoteChunk.note_id == note.id))
    session.add_all(
        NoteChunk(note_id=note.id, chunk_index=c.index, content=c.content, content_hash=c.content_hash, embedding=v)
        for c, v in zip(chunks, vectors, strict=True)
    )
    note.chunk_count = len(chunks)
    session.flush()


def clear_chunks(session: Session, note: Note) -> None:
    replace_chunks(session, note, [], [])
