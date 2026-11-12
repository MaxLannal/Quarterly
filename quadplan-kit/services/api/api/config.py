"""Typed settings read from the environment (and `.env` for local runs)."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://quarterly:quarterly@localhost:5432/quarterly"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = "quarterly"
    minio_root_password: SecretStr = SecretStr("quarterly-dev-secret")
    minio_bucket: str = "snapshots"
    server_hmac_key: SecretStr = SecretStr("dev-only-server-hmac-key")
    issuance_hmac_key: SecretStr = SecretStr("dev-only-issuance-hmac-key")
    session_secret: SecretStr = SecretStr("dev-only-session-secret")
    git_sha: str = Field(default="dev")
    environment: str = "development"
    #: Serve program versions still in `review` (labelled by their status). Only `published`
    #: versions reach students in production; M1 seed data awaits Richard's review.
    show_unpublished_programs: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
