# MindVault

AI-powered personal second brain. FastAPI + PostgreSQL/pgvector + Sentence Transformers + Ollama, with the Cosmic Intelligence UI.
One server serves both the API and the UI.

## Run (Windows PowerShell)
    docker compose -f backend\docker-compose.yml up -d     # PostgreSQL + pgvector
    ollama pull qwen2.5:1.5b                                # AI Companion model (install Ollama from ollama.com first)
    cd backend
    python -m venv .venv; .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    copy .env.example .env                                  # then set SECRET_KEY
    alembic upgrade head
    uvicorn app.main:app --port 8000

Open http://localhost:8000, create an account, and start saving notes.
The first run downloads the embedding model (~90 MB) when the first note is indexed.

## Tests
    docker compose -f backend\docker-compose.yml exec db createdb -U mindvault mindvault_test
    cd backend; pytest                  # 37 tests against real Postgres, fake embedder
    pytest -m real_model                # real MiniLM model (needs internet once)

## Low-power laptop notes (8 GB RAM, no GPU)
- Embeddings run on CPU with 2 threads (EMBEDDING_THREADS) and in batches; the model loads once, on first use.
- qwen2.5:1.5b needs about 1.5 GB; the first chat after starting Ollama is slow while it loads.
- The Universe is a lightweight 2D canvas; the starfield/orbit pause when you leave Home and respect Reduce motion.

## Optional UI smoke test (jsdom)
    npm i jsdom; python tools\e2e_server.py      # stubbed models, in one terminal
    node tools\ui_smoke.mjs                       # in another (expects the demo account in BUILD_STATUS.md)
