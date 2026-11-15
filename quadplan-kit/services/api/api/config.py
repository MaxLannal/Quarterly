"""Typed settings read from the environment (and `.env` for local runs)."""

from functools import lru_cache
from typing import Literal

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
    #: `development` and `test` are the only values that skip the start-up safety check, and
    #: they must be set explicitly: unset (or anything else) is treated as a real deployment.
    environment: str = "production"
    #: Serve program versions still in `review` (labelled by their status). Only `published`
    #: versions reach students in production; M1 seed data awaits Richard's review.
    show_unpublished_programs: bool = False

    # Accounts (prompt 04)
    #: Send the session cookie only over https. Turn off only for local http development.
    session_cookie_secure: bool = True
    session_ttl_seconds: int = 30 * 24 * 3600
    #: "console" prints codes to stdout (development only); "smtp" uses the settings below.
    email_backend: Literal["console", "smtp"] = "console"
    email_from: str = "Quarterly <no-reply@localhost>"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    #: Reverse proxies in front of the API that append the client address to X-Forwarded-For
    #: (0 = use the socket address). Used for rate limiting only; addresses are never stored.
    trusted_proxy_hops: int = 0

    # LLM agents (prompt 07)
    anthropic_api_key: SecretStr = SecretStr("")
    openrouter_api_key: SecretStr = SecretStr("")
    #: Send requests to the model providers. Off until Richard lifts the hold on API calls
    #: (CLAUDE.md, 2026-11-14): with it off the agents take their fallbacks (default elective
    #: ranking, no rationale; the advisor answers only typed confirmations).
    llm_live: bool = False
    #: "e2e": answer every model request with `api.agents.e2e_llm` (end-to-end tests of the
    #: real stack; development and test only). Never calls a provider.
    llm_fake: Literal["", "e2e"] = ""
    #: Daily model spend (USD, from llm_call) above which the worker logs LLM SPEND ALARM.
    llm_spend_alarm_usd: float = 5.0
    #: Seconds each API process keeps a catalog year in memory for loading plan inputs
    #: (api.repo.rules). 0 = always query (the default; tests rely on it).
    rules_cache_ttl_s: float = 0.0
    #: Seconds a forum page header is reused per process (api.forum.pages). 0 = off.
    page_cache_ttl_s: float = 0.0

    def production_problems(self) -> list[str]:
        """Settings that are unsafe outside development (checked at start-up)."""
        if self.environment in ("development", "test"):
            return []
        problems = [
            f"{name.upper()} still has its development value"
            for name in ("server_hmac_key", "issuance_hmac_key", "session_secret")
            if getattr(self, name).get_secret_value().startswith("dev-only-")
        ]
        if self.email_backend == "console":
            problems.append("EMAIL_BACKEND=console would print verification codes")
        if not self.session_cookie_secure:
            problems.append("SESSION_COOKIE_SECURE must be true")
        if self.llm_fake:
            problems.append("LLM_FAKE would answer students with canned test replies")
        if self.show_unpublished_programs:
            problems.append("SHOW_UNPUBLISHED_PROGRAMS would show programs no curator published")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()
