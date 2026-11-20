"""Tests never reach a real model. `.env` may turn the app's AI on for manual testing
(LLM_LIVE=true with real keys, Richard 2026-11-16); every test run gets LLM_LIVE=false and no
API keys instead. Environment variables win over `.env` in pydantic-settings, and this file
loads before any test module (it sits at pytest's rootdir)."""

import os

os.environ["LLM_LIVE"] = "false"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""
# `.env` may also turn on the API's in-memory caches for the Docker stack (RULES_CACHE_TTL_S=60,
# PAGE_CACHE_TTL_S=5); tests expect a change to show at once, so they run with both off. Tests of
# the caches set their own TTLs explicitly.
os.environ["RULES_CACHE_TTL_S"] = "0"
os.environ["PAGE_CACHE_TTL_S"] = "0"
