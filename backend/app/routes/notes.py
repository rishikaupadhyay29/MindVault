import hashlib
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.jobs import process_note
from app.models import Note, NoteAttachment, ProcessingStatus, User
from app.security import current_user
from app.services.extract import ExtractionError, extract_pdf_text
from app.services.graph import related_notes

router = APIRouter(prefix="/api", tags=["notes"])
MAX_CONTENT = 200_000


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def clean_tags(tags: list[str]) -> list[str]:
    out: list[str] = []
    for t in tags:
        t = " ".join(t.strip().split())[:40]
        if t and t.lower() not in {x.lower() for x in out}:
            out.append(t)
    return out[:20]


class NoteIn(BaseModel):
    title: str = Field("Untitled", max_length=300)
    content: str = Field("", max_length=MAX_CONTENT)
    tags: list[str] = Field(default_factory=list, max_length=50)


class NoteUpdate(BaseModel):
    title: str | None = Field(None, max_length=300)
    content: str | None = Field(None, max_length=MAX_CONTENT)
    tags: list[str] | None = Field(None, max_length=50)


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    content: str
    tags: list[str]
    source_type: str
    source_filename: str | None
    processing_status: ProcessingStatus
    processing_error: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class NoteSummary(BaseModel):
    id: uuid.UUID
    title: str
    preview: str
    tags: list[str]
    source_type: str
    source_filename: str | None
    processing_status: ProcessingStatus
    processing_error: str | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime


def _summary(n: Note) -> NoteSummary:
    return NoteSummary(id=n.id, title=n.title, preview=n.content[:200], tags=n.tags, source_type=n.source_type,
                       source_filename=n.source_filename, processing_status=n.processing_status,
                       processing_error=n.processing_error, chunk_count=n.chunk_count,
                       created_at=n.created_at, updated_at=n.updated_at)


def _get(db: Session, user: User, note_id: uuid.UUID) -> Note:
    note = db.get(Note, note_id)
    if note is None or note.owner_id != user.id:  # same 404 for "missing" and "someone else's"
        raise HTTPException(404, "Note not found")
    return note


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


@router.get("/notes", response_model=list[NoteSummary])
def list_notes(q: str | None = None, tag: str | None = None, limit: int = Query(100, ge=1, le=200),
               offset: int = Query(0, ge=0), user: User = Depends(current_user), db: Session = Depends(get_db)):
    stmt = select(Note).where(Note.owner_id == user.id)
    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(or_(Note.title.ilike(like, escape="\\"), Note.content.ilike(like, escape="\\")))
    if tag:
        stmt = stmt.where(Note.tags.any(tag))
    return [_summary(n) for n in db.scalars(stmt.order_by(Note.updated_at.desc()).limit(limit).offset(offset))]


@router.get("/tags")
def list_tags(user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = func.unnest(Note.tags).label("tag")
    sub = select(t).where(Note.owner_id == user.id).subquery()
    rows = db.execute(select(sub.c.tag, func.count()).group_by(sub.c.tag).order_by(func.count().desc(), sub.c.tag)).all()
    return [{"tag": r[0], "count": r[1]} for r in rows]


@router.get("/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _get(db, user, note_id)


@router.get("/notes/{note_id}/related")
def get_related(note_id: uuid.UUID, threshold: float = Query(0.3, ge=0, le=1),
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    _get(db, user, note_id)
    return related_notes(db, user.id, note_id, threshold)


@router.post("/notes", response_model=NoteOut, status_code=201)
def create_note(body: NoteIn, bg: BackgroundTasks, user: User = Depends(current_user), db: Session = Depends(get_db)):
    note = Note(owner_id=user.id, title=body.title.strip() or "Untitled", content=body.content,
                tags=clean_tags(body.tags), content_hash=_hash(body.content),
                processing_status=ProcessingStatus.pending, chunk_count=0)
    db.add(note)
    _commit(db)
    db.refresh(note)
    bg.add_task(process_note, note.id)
    return note


@router.put("/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: uuid.UUID, body: NoteUpdate, bg: BackgroundTasks,
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    note = _get(db, user, note_id)
    reprocess = False
    if body.title is not None:
        note.title = body.title.strip() or "Untitled"
    if body.tags is not None:
        note.tags = clean_tags(body.tags)
    if body.content is not None and _hash(body.content) != note.content_hash:
        note.content, note.content_hash = body.content, _hash(body.content)
        note.processing_status, note.processing_error = ProcessingStatus.pending, None
        reprocess = True
    note.updated_at = func.now()
    _commit(db)
    db.refresh(note)
    if reprocess:
        bg.add_task(process_note, note.id)
    return note


@router.post("/notes/{note_id}/reprocess", response_model=NoteOut)
def reprocess_note(note_id: uuid.UUID, bg: BackgroundTasks, user: User = Depends(current_user), db: Session = Depends(get_db)):
    note = _get(db, user, note_id)
    if note.processing_status == ProcessingStatus.processing:
        raise HTTPException(409, "Note is already being processed")
    note.processing_status, note.processing_error, note.indexed_hash = ProcessingStatus.pending, None, None
    _commit(db)
    db.refresh(note)
    bg.add_task(process_note, note.id)
    return note


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_get(db, user, note_id))  # chunks go via ON DELETE CASCADE
    _commit(db)
    return Response(status_code=204)


@router.post("/documents", response_model=NoteOut, status_code=201)
def upload_document(bg: BackgroundTasks, file: UploadFile = File(...), title: str = Form(""),
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    name = (file.filename or "document").replace("\\", "/").split("/")[-1][:255]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in {"pdf", "txt", "md"}:
        raise HTTPException(415, "Only PDF, TXT and Markdown files are supported.")
    limit = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB.")
    if not data:
        raise HTTPException(422, "The file is empty.")
    try:
        if ext == "pdf":
            if not data.startswith(b"%PDF-"):
                raise ExtractionError("This file is not a valid PDF.")
            text = extract_pdf_text(data)
        else:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                raise ExtractionError("Text files must be UTF-8 encoded.")
            if "\x00" in text or not text.strip():
                raise ExtractionError("No readable text found in this file.")
    except ExtractionError as e:
        raise HTTPException(422, str(e))
    text = text[:MAX_CONTENT]
    note = Note(owner_id=user.id, title=(title.strip() or name.rsplit(".", 1)[0])[:300], content=text, tags=["document"],
                source_type="document", source_filename=name, content_hash=_hash(text),
                processing_status=ProcessingStatus.pending, chunk_count=0)
    db.add(note)
    _commit(db)
    db.refresh(note)
    bg.add_task(process_note, note.id)
    return note



class AttachmentIn(BaseModel):
    document_id: uuid.UUID


@router.get("/notes/{note_id}/attachments", response_model=list[NoteSummary])
def list_attachments(
    note_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    _get(db, user, note_id)

    stmt = (
        select(Note)
        .join(NoteAttachment, NoteAttachment.document_id == Note.id)
        .where(
            NoteAttachment.note_id == note_id,
            Note.owner_id == user.id,
            Note.source_type == "document",
        )
        .order_by(NoteAttachment.created_at.desc())
    )

    return [_summary(doc) for doc in db.scalars(stmt).all()]


@router.post(
    "/notes/{note_id}/attachments",
    response_model=NoteSummary,
    status_code=201,
)
def attach_document(
    note_id: uuid.UUID,
    body: AttachmentIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    note = _get(db, user, note_id)

    if note.source_type == "document":
        raise HTTPException(400, "Attachments can only be added to regular notes.")

    document = _get(db, user, body.document_id)

    if document.source_type != "document":
        raise HTTPException(400, "Only Library documents can be attached.")

    existing = db.get(NoteAttachment, (note_id, body.document_id))
    if existing:
        return _summary(document)

    attachment = NoteAttachment(
        note_id=note_id,
        document_id=body.document_id,
    )
    db.add(attachment)
    note.updated_at = func.now()
    _commit(db)

    return _summary(document)


@router.delete(
    "/notes/{note_id}/attachments/{document_id}",
    status_code=204,
)
def detach_document(
    note_id: uuid.UUID,
    document_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    note = _get(db, user, note_id)
    document = _get(db, user, document_id)

    if document.source_type != "document":
        raise HTTPException(400, "This item is not a document.")

    attachment = db.get(NoteAttachment, (note_id, document_id))
    if attachment is None:
        raise HTTPException(404, "Attachment not found.")

    db.delete(attachment)
    note.updated_at = func.now()
    _commit(db)

    return Response(status_code=204)
