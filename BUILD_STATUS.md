# BUILD_STATUS

## Completed and tested
- Auth: register/login (scrypt + JWT), profile + preferences, password change, login lockout, per-user data isolation on every route; notes saved before accounts existed are adopted by the first account.
- Notes: CRUD, tags, Markdown (editor + safe preview), filters, validation, related notes.
- Documents: PDF / TXT / MD upload with extension, size, magic-byte and encryption checks; PDF text extraction (pypdf); background indexing.
- Pipeline: chunking, batch embeddings (all-MiniLM-L6-v2, 384-d), pgvector storage with HNSW index, status pending/processing/indexed/failed, retries with backoff, stale-edit guard, restart recovery of unfinished notes.
- Semantic search: cosine similarity over real stored chunks, best chunk per note, excerpts, scores shown as similarity (not probabilities).
- AI Companion: genuine RAG, Ollama streaming over SSE, numbered source citations, grounded vs general-knowledge labelling, conversation history, clear Ollama errors.
- Knowledge graph: note-level edges from chunk similarity via index lookups (no all-pairs scan), threshold filter, per-note related lists.
- Dashboard: database-backed metrics, recent notes, activity, discoveries, suggested questions.
- Settings (profile, workspace name, default view, reduce motion, notifications, password) and Diagnostics (API, PostgreSQL, pgvector + index, Ollama, embedding model, Redis, processing errors with Retry).
- Frontend: Cosmic design preserved; live API client, login screen, command palette (Ctrl+K).

## Test results
- Backend: 37 passed, 1 skipped (real model), real PostgreSQL 16 + pgvector 0.6, migrations tested up and down.
- End to end: migrated an existing Phase 2 database (data intact), served the UI, exercised every API over HTTP.
- UI: 18/18 checks driving the real page in jsdom (login, dashboard, library, retry, save/index, preview, tags, search, streaming chat with source chip, universe, diagnostics, settings).

## NOT verified (could not be run in the build sandbox)
- Real all-MiniLM-L6-v2 inference and real Ollama/Qwen output (tests use a deterministic fake embedder and a stub LLM; HTTP parsing of Ollama's stream is tested with a mock transport).
- Similarity defaults (search 0.15, RAG 0.25, graph 0.45, connections metric 0.5) are untuned for real MiniLM scores. Adjust RAG_MIN_SCORE / slider after trying real notes.
- A real browser, Windows, the Docker image, and performance on the i3 / 8 GB machine.

## Known limitations
- Universe is a 2D canvas; the 3D React Three Fiber version was not built.
- Original PDFs are not stored, only extracted text (no file preview); no OCR for scanned PDFs.
- Jobs run in-process (FastAPI background tasks); Redis is not used. Login rate limit is in-memory (single process).
- JWT is kept in localStorage; no email verification or password reset.
- Old chunks stay searchable until re-indexing finishes after an edit (search only uses chunks of indexed notes).
- Graph caps: 300 notes, 1500 chunks scanned. Appearance has one theme (Cosmic).
- Future features (GitHub, timeline, spaced repetition, voice, etc.) are not built.

## Next
Try with real models, tune thresholds, then consider Redis queue, file storage, 3D universe.
