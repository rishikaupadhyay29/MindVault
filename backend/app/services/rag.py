import uuid

from app.config import settings

SYSTEM_GROUNDED = (
    "You are MindVault's AI Companion. The user asks about their own saved notes.\n"
    "Answer using ONLY the numbered SOURCES below for anything about their notes, and cite them like [1] or [2].\n"
    "If the sources do not contain the answer, say you could not find it in their saved knowledge. "
    "You may then add a short answer that starts with 'From general knowledge:'. "
    "Never say something comes from their notes unless it is in the sources. Be concise.\n\nSOURCES:\n{sources}"
)
SYSTEM_UNGROUNDED = (
    "You are MindVault's AI Companion. No relevant notes were found in the user's saved knowledge for this question.\n"
    "Start by saying you couldn't find anything relevant in their notes. Then, if you can, give a brief answer that "
    "starts with 'From general knowledge:'. Never imply it came from their notes. Be concise."
)


def group_sources(chunks: list[dict]) -> list[dict]:
    """One numbered source per note; chunks of the same note are merged under its number."""
    order: dict[uuid.UUID, dict] = {}
    for c in chunks:
        s = order.setdefault(c["note_id"], dict(n=len(order) + 1, note_id=str(c["note_id"]), title=c["title"],
                                                texts=[], score=c["score"]))
        s["texts"].append(c["content"])
        s["score"] = max(s["score"], c["score"])
    return list(order.values())


def build_messages(question: str, sources: list[dict], history: list[dict]) -> list[dict]:
    if sources:
        block = "\n\n".join(f"[{s['n']}] {s['title']}\n" + "\n---\n".join(s["texts"]) for s in sources)
        system = SYSTEM_GROUNDED.format(sources=block)
    else:
        system = SYSTEM_UNGROUNDED
    hist = [{"role": m["role"], "content": m["content"][:1500]} for m in history[-6:]]
    return [{"role": "system", "content": system}, *hist, {"role": "user", "content": question}]


def public_sources(sources: list[dict]) -> list[dict]:
    return [dict(n=s["n"], note_id=s["note_id"], title=s["title"], excerpt=s["texts"][0][:240],
                 score=round(s["score"], 4)) for s in sources]
