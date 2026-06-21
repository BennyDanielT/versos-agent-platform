"""App factory + lifespan wiring. No business logic here — just composition.

Layered structure:
  core/config.py    settings
  db.py             pool + get_pool dependency
  schemas.py        request models
  services/         business logic (pure, no FastAPI) — SQL + NAT embedding
  routers/          thin HTTP layer (paths, status codes), calls services

Run:  uvicorn backend.main:app --port 8090
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import get_settings
from backend.db import create_pool
from backend.routers import agents, policy, tickets
from backend.services.nat_service import NatWorkflows


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Long-lived resources, built ONCE, shared across all requests:
    app.state.pool = await create_pool(settings.asyncpg_dsn)
    app.state.nat = NatWorkflows()
    await app.state.nat.startup(settings.triage_config_path, settings.agent_config_path)
    yield
    await app.state.nat.shutdown()
    await app.state.pool.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Versos Ops Backend", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origins,
        allow_methods=["*"], allow_headers=["*"])

    app.include_router(tickets.router)
    app.include_router(policy.router)
    app.include_router(agents.router)

    @app.get("/health", tags=["meta"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
