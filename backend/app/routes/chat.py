import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool

from app import db as dbm
from app.config import settings
from app.models import Conversation, Message, User
from app.security import current_user
from app.services import ollama, rag
from app.services.embedding import EmbeddingError
from app.services.retrieval import embed_query, retrieve_chunks

router = APIRouter(prefix="/api", tags=["chat"])


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _prepare(user_id: uuid.UUID, body: ChatIn) -> dict:
    with dbm.SessionLocal() as db:
        conv, history = None, []
        if body.conversation_id:
            conv = db.get(Conversation, body.conversation_id)
            if conv is None or conv.owner_id != user_id:
                raise HTTPException(404, "Conversation not found")
            history = [dict(role=m.role, content=m.content) for m in db.scalars(
                select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at, Message.id))]
        try:
            vec = embed_query(body.message)
        except EmbeddingError as e:
            raise HTTPException(503, f"Knowledge search is unavailable right now: {e}")
        chunks = [c for c in retrieve_chunks(db, user_id, vec, settings.rag_top_k * 2) if c["score"] >= settings.rag_min_score]
        sources = rag.group_sources(chunks[: settings.rag_top_k])
        if conv is None:
            conv = Conversation(owner_id=user_id, title=body.message.strip()[:60])
            db.add(conv)
            db.flush()
        db.add(Message(conversation_id=conv.id, role="user", content=body.message))
        conv.updated_at = func.now()
        db.commit()
        return dict(conversation_id=conv.id, sources=sources, messages=rag.build_messages(body.message, sources, history))


def _save_reply(conversation_id: uuid.UUID, text: str, sources: list[dict]) -> uuid.UUID:
    with dbm.SessionLocal() as db:
        msg = Message(conversation_id=conversation_id, role="assistant", content=text,
                      sources=rag.public_sources(sources), grounded=bool(sources))
        db.add(msg)
        conv = db.get(Conversation, conversation_id)
        if conv:
            conv.updated_at = func.now()
        db.commit()
        return msg.id


@router.post("/chat/stream")
async def chat_stream(body: ChatIn, user: User = Depends(current_user)):
    prep = await run_in_threadpool(_prepare, user.id, body)
    client = ollama.get_ollama()

    async def events():
        yield _sse("meta", dict(conversation_id=str(prep["conversation_id"]), grounded=bool(prep["sources"]),
                                sources=rag.public_sources(prep["sources"])))
        parts: list[str] = []
        try:
            async for tok in client.stream_chat(prep["messages"]):
                parts.append(tok)
                yield _sse("token", {"t": tok})
        except ollama.OllamaError as e:
            yield _sse("error", {"message": str(e)})
            return
        text = "".join(parts).strip()
        if not text:
            yield _sse("error", {"message": "The model returned an empty answer. Try again."})
            return
        mid = await run_in_threadpool(_save_reply, prep["conversation_id"], text, prep["sources"])
        yield _sse("done", {"message_id": str(mid)})

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/conversations")
def list_conversations(user: User = Depends(current_user)):
    with dbm.SessionLocal() as db:
        rows = db.scalars(select(Conversation).where(Conversation.owner_id == user.id)
                          .order_by(Conversation.updated_at.desc()).limit(50)).all()
        return [dict(id=str(c.id), title=c.title, updated_at=c.updated_at.isoformat()) for c in rows]


def _owned(db, user: User, cid: uuid.UUID) -> Conversation:
    conv = db.get(Conversation, cid)
    if conv is None or conv.owner_id != user.id:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.get("/conversations/{cid}")
def get_conversation(cid: uuid.UUID, user: User = Depends(current_user)):
    with dbm.SessionLocal() as db:
        conv = _owned(db, user, cid)
        msgs = db.scalars(select(Message).where(Message.conversation_id == cid).order_by(Message.created_at, Message.id))
        return dict(id=str(conv.id), title=conv.title, messages=[
            dict(id=str(m.id), role=m.role, content=m.content, sources=m.sources, grounded=m.grounded,
                 created_at=m.created_at.isoformat()) for m in msgs])


@router.delete("/conversations/{cid}", status_code=204)
def delete_conversation(cid: uuid.UUID, user: User = Depends(current_user)):
    with dbm.SessionLocal() as db:
        db.delete(_owned(db, user, cid))
        db.commit()
    return Response(status_code=204)
