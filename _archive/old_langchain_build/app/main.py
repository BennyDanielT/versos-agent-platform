"""FastAPI application entrypoint.

Run locally:
    docker compose up -d          # postgres + localstack
    uvicorn app.main:app --reload
    open http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.db import engine
from app.routers import assets, audit, tickets


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast if the DB isn't reachable, rather than 500ing on first request.
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    await engine.dispose()


app = FastAPI(
    title="Versos Agent-Ops Platform",
    version="0.1.0",
    summary="Support triage + media enrichment + quality auditing on one agent substrate.",
    lifespan=lifespan,
)

app.include_router(tickets.router)
app.include_router(assets.router)
app.include_router(audit.router)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}
