import asyncio
import threading
from functools import lru_cache

from app.config import settings


class EmbeddingError(RuntimeError):
    pass


class EmbeddingService:
    """Loads the model once (thread-safe, lazily) and embeds batches. embed() is blocking:
    call it from a worker thread (BackgroundTasks does) or use aembed()."""

    def __init__(self, model_name: str, dim: int, batch_size: int):
        self.model_name, self.dim, self.batch_size = model_name, dim, batch_size
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        import torch
                        from sentence_transformers import SentenceTransformer

                        torch.set_num_threads(settings.embedding_threads)  # leave CPU for Ollama / the UI

                        self._model = SentenceTransformer(self.model_name, device="cpu")
                    except Exception as e:
                        raise EmbeddingError(f"Embedding model could not be loaded: {e}") from e
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        try:
            arr = model.encode(
                texts,
                batch_size=self.batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            vectors = arr.tolist()
        except Exception as e:
            raise EmbeddingError(f"Embedding generation failed: {e}") from e
        if len(vectors) != len(texts) or any(len(v) != self.dim for v in vectors):
            raise EmbeddingError(f"Model returned unexpected shape (expected {self.dim} dims)")
        return vectors

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self.embed, texts)


@lru_cache(maxsize=1)
def get_embedder() -> EmbeddingService:
    return EmbeddingService(settings.embedding_model, settings.embedding_dim, settings.embedding_batch_size)
