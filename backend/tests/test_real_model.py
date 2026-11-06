import pytest

from app.services.embedding import EmbeddingError, get_embedder

pytestmark = pytest.mark.real_model


def test_real_model_returns_384_dims_and_ranks_by_meaning():
    try:
        v = get_embedder().embed(["PostgreSQL indexes speed up queries", "How do I make database queries faster?",
                                  "Banana bread recipe with walnuts"])
    except EmbeddingError as e:
        pytest.skip(f"model unavailable here: {e}")
    assert all(len(x) == 384 for x in v)
    dot = lambda a, b: sum(x * y for x, y in zip(a, b))
    assert dot(v[0], v[1]) > dot(v[0], v[2])
