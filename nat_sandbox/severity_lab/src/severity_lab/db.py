"""Single source of truth for the asyncpg DSN used by the NAT function configs.

The FastAPI backend reads DATABASE_URL via pydantic-settings, but the NAT function
configs are built from YAML and never saw it — so in a container they silently fell
back to localhost and the workflow failed to build (ConnectionRefusedError).

Defaulting to the environment keeps local dev unchanged (no DATABASE_URL set →
the docker-compose DSN) while letting ECS/App Runner inject the real endpoint.
Any YAML that sets `database_url:` explicitly still wins.
"""
import os

LOCAL_DSN = "postgresql://versos:versos@localhost:5432/versos"


def default_database_url() -> str:
    """The DSN from the environment, falling back to the local docker Postgres."""
    return os.getenv("DATABASE_URL", LOCAL_DSN)
