"""App settings — typed, env-driven, single source of truth."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://versos:versos@localhost:5432/versos"
    configs_dir: str = "nat_sandbox/severity_lab/src/severity_lab/configs"
    cors_origins: list[str] = ["*"]   # Next.js dev server; tighten in prod

    @property
    def asyncpg_dsn(self) -> str:
        # .env may hold a SQLAlchemy-style DSN; asyncpg needs plain postgresql://
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")

    @property
    def triage_config_path(self) -> str:
        return f"{self.configs_dir}/triage_direct.yml"

    @property
    def agent_config_path(self) -> str:
        return f"{self.configs_dir}/agent.yml"


@lru_cache
def get_settings() -> Settings:
    return Settings()
