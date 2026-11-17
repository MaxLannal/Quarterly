"""Tests never reach a real model. `.env` may turn the app's AI on for manual testing
(LLM_LIVE=true with real keys, Richard 2026-11-16); every test run gets LLM_LIVE=false and no
API keys instead. Environment variables win over `.env` in pydantic-settings, and this file
loads before any test module (it sits at pytest's rootdir)."""

import os

os.environ["LLM_LIVE"] = "false"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["OPENROUTER_API_KEY"] = ""
