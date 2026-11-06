import io

from pypdf import PdfWriter

from app.config import settings
from tests.conftest import add_note, chunk_rows, make_pdf


def test_tags_filters_and_validation(client, embedder):
    a = add_note(client, "A", "# Heading\n\n**bold** text", ["Python", " python ", "web dev", ""])
    add_note(client, "B", "other", ["rust"])
    note = client.get(f"/api/notes/{a}").json()
    assert note["tags"] == ["Python", "web dev"] and "**bold**" in note["content"]  # markdown stored raw
    assert [n["title"] for n in client.get("/api/notes", params={"tag": "rust"}).json()] == ["B"]
    assert [n["title"] for n in client.get("/api/notes", params={"q": "bold"}).json()] == ["A"]
    assert client.get("/api/notes", params={"q": "100%"}).json() == []  # wildcard chars are escaped
    assert {t["tag"]: t["count"] for t in client.get("/api/tags").json()} == {"Python": 1, "web dev": 1, "rust": 1}
    client.put(f"/api/notes/{a}", json={"tags": ["new"]})
    assert client.get(f"/api/notes/{a}").json()["tags"] == ["new"]
    assert client.post("/api/notes", json={"title": "x" * 301}).status_code == 422
    assert client.post("/api/notes", json={"content": "x" * 200_001}).status_code == 422
    assert client.get("/api/notes/not-a-uuid").status_code == 422


def test_isolation_between_users(client, client2, embedder):
    nid = add_note(client, "Private", "secret")
    assert client2.get("/api/notes").json() == []
    assert client2.get(f"/api/notes/{nid}").status_code == 404
    assert client2.put(f"/api/notes/{nid}", json={"title": "hax"}).status_code == 404
    assert client2.delete(f"/api/notes/{nid}").status_code == 404
    assert client2.post(f"/api/notes/{nid}/reprocess").status_code == 404
    assert client.get(f"/api/notes/{nid}").json()["title"] == "Private"


def test_pdf_upload_extracts_and_indexes(client, embedder):
    r = client.post("/api/documents", files={"file": ("Postgres Guide.pdf", make_pdf("Indexes speed up queries"), "application/pdf")})
    assert r.status_code == 201
    n = client.get(f"/api/notes/{r.json()['id']}").json()
    assert n["source_type"] == "document" and n["title"] == "Postgres Guide" and "Indexes speed up queries" in n["content"]
    assert n["processing_status"] == "indexed" and len(chunk_rows(n["id"])) == n["chunk_count"] >= 1


def test_text_upload_and_rejections(client, embedder, monkeypatch):
    ok = client.post("/api/documents", files={"file": ("n.md", b"# hi\nsome text", "text/markdown")})
    assert ok.status_code == 201
    assert client.post("/api/documents", files={"file": ("evil.exe", b"MZ", "application/octet-stream")}).status_code == 415
    assert client.post("/api/documents", files={"file": ("fake.pdf", b"not a pdf", "application/pdf")}).status_code == 422
    assert client.post("/api/documents", files={"file": ("e.txt", b"", "text/plain")}).status_code == 422
    blank = io.BytesIO()
    w = PdfWriter(); w.add_blank_page(612, 792); w.write(blank)
    r = client.post("/api/documents", files={"file": ("scan.pdf", blank.getvalue(), "application/pdf")})
    assert r.status_code == 422 and "No selectable text" in r.json()["detail"]
    monkeypatch.setattr(settings, "max_upload_mb", 0)
    assert client.post("/api/documents", files={"file": ("big.txt", b"abc", "text/plain")}).status_code == 413
