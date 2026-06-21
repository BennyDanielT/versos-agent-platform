"""Database plumbing: pool creation + a FastAPI dependency to inject it."""
import asyncpg
from fastapi import Request


async def create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn)


def get_pool(request: Request) -> asyncpg.Pool:
    """Dependency: hands routers the shared pool created in the app lifespan."""
    return request.app.state.pool
