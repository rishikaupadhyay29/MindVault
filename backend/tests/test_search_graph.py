from app.services import embedding
from app.services.embedding import EmbeddingError
from tests.conftest import COOK, DB_TEXT, DB_TEXT2, add_note, make_client


def seed(client):
    return add_note(client, "Postgres indexes", DB_TEXT), add_note(client, "Query tuning", DB_TEXT2), add_note(client, "Bread", COOK)


def test_semantic_search_ranks_and_scopes(client, client2, embedder):
    db1, db2, bread = seed(client)
    res = client.get("/api/search", params={"q": "how do database indexes speed up queries"}).json()["results"]
    assert res[0]["note_id"] in (db1, db2) and res[0]["score"] > 0.3 and "excerpt" in res[0]
    assert [r["score"] for r in res] == sorted((r["score"] for r in res), reverse=True)
    assert bread not in [r["note_id"] for r in res[:2]]
    assert len({r["note_id"] for r in res}) == len(res)  # one hit per note
    assert client2.get("/api/search", params={"q": "database indexes"}).json()["results"] == []


def test_search_ignores_unindexed_notes_and_handles_errors(client, embedder, monkeypatch):
    seed(client)
    class Broken:
        def embed(self, t):
            raise EmbeddingError("model down")
    monkeypatch.setattr(embedding, "get_embedder", lambda: Broken())
    failed = add_note(client, "Never indexed", "database database database indexes")
    assert client.get(f"/api/notes/{failed}").json()["processing_status"] == "failed"
    r = client.get("/api/search", params={"q": "database indexes"})
    assert r.status_code == 503 and "model down" in r.json()["detail"]
    monkeypatch.setattr(embedding, "get_embedder", lambda: embedder)
    ids = [x["note_id"] for x in client.get("/api/search", params={"q": "database indexes"}).json()["results"]]
    assert failed not in ids
    assert client.get("/api/search", params={"q": "a"}).status_code == 422


def test_graph_connects_only_similar_notes(client, client2, embedder):
    db1, db2, bread = seed(client)
    g = client.get("/api/graph", params={"threshold": 0.33}).json()
    pairs = {frozenset((e["source"], e["target"])) for e in g["edges"]}
    assert frozenset((db1, db2)) in pairs
    assert not any(bread in p for p in pairs)  # no fabricated relationships
    assert {n["id"] for n in g["nodes"]} == {db1, db2, bread}
    assert all(0.33 <= e["score"] <= 1 for e in g["edges"])
    assert client.get("/api/graph", params={"threshold": 0.95}).json()["edges"] == []
    assert client2.get("/api/graph").json() == {"nodes": [], "edges": [], "threshold": 0.45}
    rel = client.get(f"/api/notes/{db1}/related", params={"threshold": 0.33}).json()
    assert [r["id"] for r in rel] == [db2]
    assert client2.get(f"/api/notes/{db1}/related").status_code == 404


def test_single_note_has_no_edges(client, embedder):
    add_note(client, "Only", DB_TEXT)
    assert client.get("/api/graph", params={"threshold": 0.1}).json()["edges"] == []
