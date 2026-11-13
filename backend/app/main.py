import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import jobs
from app.config import settings
from app.routes import auth, chat, collections, graph, notes, search, stats

log = logging.getLogger("mindvault")
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.secret_key == "dev-secret-change-me":
        if settings.environment == "production":
            raise RuntimeError("Set SECRET_KEY in .env before running in production.")
        log.warning("Using the development SECRET_KEY. Set SECRET_KEY in .env.")
    ids = jobs.recover_stuck()
    if ids:
        log.info("re-queueing %s unfinished notes", len(ids))
        threading.Thread(target=lambda: [jobs.process_note(i) for i in ids], daemon=True).start()
    yield


app = FastAPI(title="MindVault API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","), allow_methods=["*"],
                   allow_headers=["*"])
for r in (auth, notes, search, graph, chat, stats, collections):    app.include_router(r.router)


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok"}


if FRONTEND.exists():  # one command serves both API and UI
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
