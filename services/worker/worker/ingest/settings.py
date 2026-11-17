"""Settings for the catalog pipeline, read from the environment (and `.env`).

Everything is off by default: the cron jobs do nothing unless `CATALOG_INGEST_ENABLED=true`,
and the agents call a model only with `LLM_LIVE=true` (the API hold, 2026-11-14)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

#: The crawler never goes faster than this, whatever the settings say (SPEC: 1 request/second).
MIN_INTERVAL_S = 1.0


class IngestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    #: Run the annual catalog job and the monthly change check (Arq cron). Off by default.
    catalog_ingest_enabled: bool = False
    catalog_base_url: str = "https://collegecatalog.uchicago.edu"
    #: The College page that states how many majors and minors there are (one of the
    #: independent lists the program count must match).
    catalog_counts_url: str = "https://college.uchicago.edu/academics/programs-study"
    #: Contact address sent in the crawler's user agent so the site's operators can reach us.
    #: Required before any request is made. Never logged.
    catalog_contact_email: str = ""
    catalog_request_interval_s: float = Field(default=MIN_INTERVAL_S, ge=MIN_INTERVAL_S)
    #: The catalog year the annual run writes (for example 2027-28). Empty: the year after
    #: the newest catalog year in the database.
    catalog_target_year: str = ""
    #: Stop the agents once this much has been spent in one run (list prices, USD).
    ingest_cost_cap_usd: float = Field(default=25.0, ge=0)

    database_url: str = "postgresql+psycopg://quarterly:quarterly@localhost:5432/quarterly"
    minio_endpoint: str = "localhost:9000"
    minio_root_user: str = "quarterly"
    minio_root_password: SecretStr = SecretStr("quarterly-dev-secret")
    minio_bucket: str = "snapshots"
    minio_secure: bool = False

    llm_live: bool = False
    anthropic_api_key: SecretStr = SecretStr("")
    openrouter_api_key: SecretStr = SecretStr("")


@lru_cache
def get_ingest_settings() -> IngestSettings:
    return IngestSettings()
