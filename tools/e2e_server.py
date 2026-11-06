import sys, re, hashlib, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import uvicorn
from app.main import app
from app.services import embedding, ollama
class Fake:
    def embed(self, texts):
        out = []
        for t in texts:
            v = [0.0] * 384
            for w in re.findall(r"\w+", t.lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 384] += 1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out
class LLM:
    async def stream_chat(self, m):
        for t in ("Indexes ", "speed up queries [1]."):
            yield t
    async def status(self): return {"status": "ok", "url": "stub", "model": "qwen2.5:1.5b"}
f = Fake(); embedding.get_embedder = lambda: f; ollama.get_ollama = lambda: LLM()
uvicorn.run(app, port=8000, log_level="warning")
