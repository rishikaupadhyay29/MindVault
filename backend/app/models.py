import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.db import Base


class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    indexed = "indexed"
    failed = "failed"


def _id():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _ts():
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _id()
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    display_name: Mapped[str] = mapped_column(String(80), default="")
    prefs: Mapped[dict] = mapped_column("settings", JSONB, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = _ts()


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[uuid.UUID] = _id()
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300), default="Untitled")
    content: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(50)), default=list, server_default=text("'{}'"))
    source_type: Mapped[str] = mapped_column(String(20), default="note", server_default="note")
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    indexed_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status", values_callable=lambda e: [x.value for x in e]),
        default=ProcessingStatus.pending)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()
    chunks: Mapped[list["NoteChunk"]] = relationship(back_populates="note", passive_deletes=True)


class NoteChunk(Base):
    __tablename__ = "note_chunks"
    __table_args__ = (UniqueConstraint("note_id", "chunk_index", name="uq_note_chunks_note_idx"),)
    id: Mapped[uuid.UUID] = _id()
    note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notes.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding = mapped_column(Vector(settings.embedding_dim), nullable=False)
    created_at: Mapped[datetime] = _ts()
    note: Mapped[Note] = relationship(back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = _id()
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120), default="New conversation")
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _ts()


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = _id()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    grounded: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = _ts()

class NoteAttachment(Base):
    __tablename__ = "note_attachments"

    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        primary_key=True,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notes.id", ondelete="CASCADE"),
        primary_key=True,
    )

    created_at: Mapped[datetime] = _ts()
