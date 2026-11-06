import os

os.environ["EMBED_RETRY_DELAY"] = "0"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://mindvault:mindvault@localhost:5432/mindvault_test"
)
import hashlib
import math
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import db
from app.main import app
from app.services import embedding


class FakeEmbedder:
    """Deterministic 384-d bag-of-words vectors. Real DB, fake model."""

    def embed(self, texts):
        out = []
        for t in texts:
            v = [0.0] * 384
            for w in re.findall(r"\w+", t.lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 384] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out


@pytest.fixture(scope="session", autouse=True)
def migrated():
    cfg = Config(str(Path(__file__).parent.parent / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).parent.parent / "migrations"))
    command.downgrade(cfg, "base")  # exercises both directions of the migration
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def clean():
    with db.engine.begin() as c:
        c.execute(text("TRUNCATE note_chunks, notes, messages, conversations, users CASCADE"))
    from app.routes import auth
    auth._fails.clear()


@pytest.fixture
def embedder(monkeypatch):
    fake = FakeEmbedder()
    monkeypatch.setattr(embedding, "get_embedder", lambda: fake)
    return fake


def make_client(email="a@example.com"):
    c = TestClient(app)
    r = c.post("/api/auth/register", json={"email": email, "password": "correct-horse", "display_name": "Tester"})
    assert r.status_code == 201, r.text
    c.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    return c


@pytest.fixture
def client():
    return make_client()


@pytest.fixture
def client2():
    return make_client("b@example.com")


def make_pdf(text):
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, x)


def add_note(c, title, content, tags=None):
    r = c.post("/api/notes", json={"title": title, "content": content, "tags": tags or []})
    assert r.status_code == 201, r.text
    return r.json()["id"]


DB_TEXT = "PostgreSQL indexes speed up database queries. A B-tree index reduces the rows scanned by a query."
DB_TEXT2 = "Database query performance improves with indexes. Use EXPLAIN ANALYZE to find slow database queries."
COOK = "Sourdough bread needs a ripe starter, flour, water and salt. Bake the bread in a hot dutch oven."


def chunk_rows(note_id):
    with db.engine.connect() as c:
        return c.execute(
            text("SELECT id, chunk_index, content, vector_dims(embedding) AS dims FROM note_chunks "
                 "WHERE note_id = :n ORDER BY chunk_index"), {"n": str(note_id)}).all()
