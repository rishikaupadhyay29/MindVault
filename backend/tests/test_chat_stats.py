import json
import uuid

import httpx
import pytest

from app import jobs
from app.models import Note, ProcessingStatus
from app import db as dbm
from app.services import ollama
from app.services.ollama import OllamaClient, OllamaError
from tests.conftest import COOK, DB_TEXT, DB_TEXT2, add_note, make_client


class FakeLLM:
    def __init__(self, tokens=("Indexes ", "help [1]."), error=None):
        self.tokens, self.error, self.calls = tokens, error, []

    async def stream_chat(self, messages):
        self.calls.append(messages)
        for t in self.tokens:
            yield t
        if self.error:
            raise OllamaError(self.error)


def events(client, **body):
    out = []
    with client.stream("POST", "/api/chat/stream", json=body) as r:
        assert r.status_code == 200, r.read()
        ev = None
        for line in r.iter_lines():
            if line.startswith("event: "):
                ev = line[7:]
            elif line.startswith("data: "):
                out.append((ev, json.loads(line[6:])))
    return out


def test_grounded_answer_streams_with_sources_and_persists(client, embedder, monkeypatch):
    nid = add_note(client, "Postgres indexes", DB_TEXT)
    add_note(client, "Bread", COOK)
    llm = FakeLLM()
    monkeypatch.setattr(ollama, "get_ollama", lambda: llm)
    ev = events(client, message="How do database indexes speed up queries?")
    assert [e for e, _ in ev] == ["meta", "token", "token", "done"]
    meta = ev[0][1]
    assert meta["grounded"] and [s["note_id"] for s in meta["sources"]] == [nid] and meta["sources"][0]["n"] == 1
    system = llm.calls[0][0]["content"]
    assert "B-tree index" in system and "ONLY the numbered SOURCES" in system and "sourdough" not in system.lower()
    conv = client.get(f"/api/conversations/{meta['conversation_id']}").json()
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant"]
    assert conv["messages"][1]["content"] == "Indexes help [1]." and conv["messages"][1]["sources"][0]["title"] == "Postgres indexes"
    # follow-up keeps history
    events(client, message="Tell me more about database indexes", conversation_id=meta["conversation_id"])
    assert any(m["content"] == "Indexes help [1]." for m in llm.calls[1])
    assert [c["id"] for c in client.get("/api/conversations").json()] == [meta["conversation_id"]]


def test_no_relevant_notes_is_not_presented_as_grounded(client, embedder, monkeypatch):
    add_note(client, "Bread", COOK)
    llm = FakeLLM()
    monkeypatch.setattr(ollama, "get_ollama", lambda: llm)
    meta = events(client, message="quantum chromodynamics gluon confinement")[0][1]
    assert meta["grounded"] is False and meta["sources"] == []
    assert "No relevant notes were found" in llm.calls[0][0]["content"] and "sourdough" not in llm.calls[0][0]["content"].lower()
    conv = client.get(f"/api/conversations/{meta['conversation_id']}").json()
    assert conv["messages"][1]["grounded"] is False


def test_llm_errors_surface_and_nothing_fake_is_saved(client, embedder, monkeypatch):
    add_note(client, "Postgres indexes", DB_TEXT)
    monkeypatch.setattr(ollama, "get_ollama", lambda: FakeLLM(tokens=(), error="Can't reach Ollama"))
    ev = events(client, message="database indexes")
    assert ev[-1][0] == "error" and "Ollama" in ev[-1][1]["message"]
    conv = client.get(f"/api/conversations/{ev[0][1]['conversation_id']}").json()
    assert [m["role"] for m in conv["messages"]] == ["user"]


def test_conversation_isolation_and_delete(client, client2, embedder, monkeypatch):
    add_note(client, "Postgres indexes", DB_TEXT)
    monkeypatch.setattr(ollama, "get_ollama", lambda: FakeLLM())
    cid = events(client, message="database indexes")[0][1]["conversation_id"]
    assert client2.get(f"/api/conversations/{cid}").status_code == 404
    assert client2.delete(f"/api/conversations/{cid}").status_code == 404
    assert client2.post("/api/chat/stream", json={"message": "hi", "conversation_id": cid}).status_code == 404
    assert client2.get("/api/conversations").json() == []
    assert client.delete(f"/api/conversations/{cid}").status_code == 204
    assert client.get("/api/conversations").json() == []
    assert client.post("/api/chat/stream", json={"message": ""}).status_code == 422


def test_ollama_client_parses_ndjson_and_maps_errors():
    import asyncio

    def handler(req):
        body = json.loads(req.content)
        assert body["model"] == "qwen2.5:1.5b" and body["stream"] is True
        lines = [{"message": {"content": "Hel"}}, {"message": {"content": "lo"}}, {"done": True}]
        return httpx.Response(200, content="\n".join(json.dumps(x) for x in lines))

    async def collect(client):
        return [t async for t in client.stream_chat([{"role": "user", "content": "x"}])]

    ok = OllamaClient("http://x", "qwen2.5:1.5b", 5, httpx.MockTransport(handler))
    assert "".join(asyncio.run(collect(ok))) == "Hello"
    missing = OllamaClient("http://x", "qwen2.5:1.5b", 5, httpx.MockTransport(lambda r: httpx.Response(404)))
    with pytest.raises(OllamaError, match="ollama pull"):
        asyncio.run(collect(missing))
    def refuse(req):
        raise httpx.ConnectError("refused")
    down = OllamaClient("http://x", "m", 5, httpx.MockTransport(refuse))
    with pytest.raises(OllamaError, match="Is it running"):
        asyncio.run(collect(down))
    assert asyncio.run(down.status())["status"] == "unreachable"


def test_stats_are_real_and_scoped(client, client2, embedder):
    add_note(client, "Postgres indexes", DB_TEXT, ["db"])
    add_note(client, "Query tuning", DB_TEXT + " Indexes matter.")
    add_note(client, "Bread", COOK)
    client.post("/api/documents", files={"file": ("d.txt", b"plain document text here", "text/plain")})
    s = client.get("/api/stats").json()
    assert (s["notes"], s["indexed"], s["failed"], s["documents"]) == (4, 4, 0, 1)
    assert s["chunks"] >= 4 and s["connections"] >= 1 and len(s["recent"]) == 4
    assert s["discoveries"][0]["a_title"] and s["activity"] and s["suggestions"]
    z = client2.get("/api/stats").json()
    assert (z["notes"], z["chunks"], z["connections"], z["recent"], z["discoveries"]) == (0, 0, 0, [], [])


def test_diagnostics_shape(client, embedder):
    d = client.get("/api/diagnostics").json()
    assert d["postgres"]["status"] == "ok" and d["pgvector"]["status"] == "ok" and d["pgvector"]["indexes"]
    assert d["ollama"]["status"] in ("unreachable", "ok", "model_missing")
    assert d["embedding"]["dimensions"] == 384 and d["redis"]["status"] == "not_used"
    assert make_client("z@example.com") and client.get("/api/diagnostics").status_code == 200


def test_recover_stuck_notes_after_restart(client, embedder):
    nid = add_note(client, "Stuck", DB_TEXT)
    with dbm.SessionLocal() as s:
        n = s.get(Note, uuid.UUID(nid))
        n.processing_status, n.indexed_hash = ProcessingStatus.processing, None
        s.commit()
    ids = jobs.recover_stuck()
    assert [str(i) for i in ids] == [nid]
    for i in ids:
        jobs.process_note(i)
    assert client.get(f"/api/notes/{nid}").json()["processing_status"] == "indexed"
