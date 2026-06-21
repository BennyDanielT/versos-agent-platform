"""Centralised settings, loaded from environment / .env.

Using pydantic-settings means every config value is typed and validated at
startup — if DATABASE_URL is missing you find out immediately, not on first query.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://versos:versos@localhost:5432/versos"

    aws_region: str = "us-east-1"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"
    s3_endpoint_url: str | None = "http://localhost:4566"
    s3_bucket: str = "versos-media"

    # LLM — NVIDIA NIM (https://build.nvidia.com). Required for agent endpoints.
    nvidia_api_key: str | None = None
    nvidia_model: str = "meta/llama-3.3-70b-instruct"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"

    langchain_tracing_v2: bool = False
    langchain_project: str = "versos-platform"


@lru_cache
def get_settings() -> Settings:
    return Settings()
