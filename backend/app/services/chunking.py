"""Pure text chunking: no I/O, no database."""
import hashlib
import re
from dataclasses import dataclass

_SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Chunk:
    index: int
    content: str
    content_hash: str


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _units(text: str, size: int) -> list[str]:
    """Paragraphs, falling back to sentences, falling back to hard cuts. Each unit <= size."""
    out: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= size:
            out.append(para)
            continue
        for sent in _SENTENCE.split(para):
            sent = sent.strip()
            while len(sent) > size:
                cut = sent.rfind(" ", 0, size)
                cut = cut if cut > size // 2 else size
                out.append(sent[:cut].strip())
                sent = sent[cut:].strip()
            if sent:
                out.append(sent)
    return out


def _tail(s: str, n: int) -> str:
    if n <= 0 or len(s) <= n:
        return "" if n <= 0 else s
    t = s[-n:]
    i = t.find(" ")
    return t[i + 1:] if i != -1 else t


def chunk_text(text: str | None, size: int = 800, overlap: int = 120) -> list[Chunk]:
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("need size > 0 and 0 <= overlap < size")
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        return []

    raw: list[str] = []
    cur = ""
    for unit in _units(text, size):
        if cur and len(cur) + 1 + len(unit) > size:
            raw.append(cur)
            tail = _tail(cur, overlap)
            cur = f"{tail} {unit}".strip() if tail else unit
            if len(cur) > size:  # overlap must never push a chunk over the limit
                cur = unit
        else:
            cur = f"{cur}\n{unit}" if cur else unit
    if cur:
        raw.append(cur)

    seen: set[str] = set()
    chunks: list[Chunk] = []
    for c in raw:
        h = hashlib.sha256(_norm(c).encode()).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        chunks.append(Chunk(len(chunks), c, h))
    return chunks
