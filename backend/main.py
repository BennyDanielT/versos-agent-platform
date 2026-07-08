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
from backend.migrate import run_migrations
from backend.routers import admin, agents, index_ops, pipeline_ops, policy, sim, tickets
from backend.services.nat_service import NatWorkflows
from backend.services.simulator import Simulator


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Long-lived resources, built ONCE, shared across all requests:
    app.state.pool = await create_pool(settings.asyncpg_dsn)
    if settings.run_migrations:
        await run_migrations(app.state.pool, settings.sql_dir)
    app.state.nat = NatWorkflows()
    await app.state.nat.startup(settings.triage_config_path, settings.agent_config_path)
    # Live data simulator (idle until /sim/start). Feeds the real pipeline, not fake rows.
    app.state.sim = Simulator(
        app.state.pool, settings.asyncpg_dsn, triage_getter=lambda: app.state.nat.triage)
    yield
    await app.state.sim.stop()
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
    app.include_router(index_ops.router)
    app.include_router(pipeline_ops.router)
    app.include_router(sim.router)
    app.include_router(admin.router)

    @app.get("/health", tags=["meta"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
