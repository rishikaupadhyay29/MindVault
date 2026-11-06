import pytest

from app.services.chunking import chunk_text


def norm(s):
    return " ".join(s.split())


def test_empty_and_whitespace():
    assert chunk_text("") == [] and chunk_text("  \n\n ") == [] and chunk_text(None) == []


def test_short_text_is_one_chunk():
    c = chunk_text("Hello world.")
    assert len(c) == 1 and c[0].content == "Hello world."


def test_size_limit_and_overlap():
    text = " ".join(f"Sentence number {i} talks about databases and indexes." for i in range(60))
    chunks = chunk_text(text, size=200, overlap=40)
    assert len(chunks) > 3
    assert all(len(c.content) <= 200 for c in chunks)
    for a, b in zip(chunks, chunks[1:]):
        last = " ".join(norm(a.content).split()[-3:])
        assert last in norm(b.content)[:60], "neighbouring chunks must overlap"


def test_duplicates_removed():
    para = "The same paragraph repeated again and again here."
    chunks = chunk_text("\n\n".join([para] * 12), size=100, overlap=20)
    norms = [norm(c.content).lower() for c in chunks]
    assert len(set(norms)) == len(norms) and len(chunks) < 12


def test_long_unbroken_text_is_split():
    text = "".join(chr(97 + i % 26) for i in range(2500))
    chunks = chunk_text(text, size=800, overlap=100)
    assert len(chunks) >= 3 and all(len(c.content) <= 800 for c in chunks)


def test_deterministic_and_validates_args():
    t = "Alpha beta gamma. " * 100
    assert chunk_text(t, 150, 30) == chunk_text(t, 150, 30)
    with pytest.raises(ValueError):
        chunk_text("x", size=100, overlap=100)
