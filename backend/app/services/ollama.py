import json
from collections.abc import AsyncIterator

import httpx

from app.config import settings


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: float, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url, self.model, self.timeout, self.transport = base_url.rstrip("/"), model, timeout, transport

    def _client(self, timeout=None):
        return httpx.AsyncClient(base_url=self.base_url, transport=self.transport,
                                 timeout=httpx.Timeout(timeout or self.timeout, connect=5.0))

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        body = {"model": self.model, "messages": messages, "stream": True,
                "options": {"num_ctx": 2048, "temperature": 0.3}}
        try:
            async with self._client() as c, c.stream("POST", "/api/chat", json=body) as r:
                if r.status_code == 404:
                    raise OllamaError(f"Model '{self.model}' is not installed. Run: ollama pull {self.model}")
                if r.status_code >= 400:
                    raise OllamaError(f"Ollama returned HTTP {r.status_code}.")
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    d = json.loads(line)
                    if d.get("error"):
                        raise OllamaError(str(d["error"]))
                    piece = (d.get("message") or {}).get("content")
                    if piece:
                        yield piece
                    if d.get("done"):
                        return
        except httpx.ConnectError as e:
            raise OllamaError(f"Can't reach Ollama at {self.base_url}. Is it running?") from e
        except httpx.TimeoutException as e:
            raise OllamaError("Ollama took too long to respond. The first request after startup loads the model.") from e

    async def status(self) -> dict:
        try:
            async with self._client(5.0) as c:
                r = await c.get("/api/tags")
                r.raise_for_status()
                names = [m.get("name", "") for m in r.json().get("models", [])]
        except Exception as e:
            return {"status": "unreachable", "url": self.base_url, "model": self.model, "detail": str(e)[:200]}
        ok = any(n == self.model or n.split(":")[0] == self.model for n in names)
        return {"status": "ok" if ok else "model_missing", "url": self.base_url, "model": self.model, "installed_models": names,
                **({} if ok else {"detail": f"Run: ollama pull {self.model}"})}


def get_ollama() -> OllamaClient:
    return OllamaClient(settings.ollama_url, settings.ollama_model, settings.ollama_timeout)
