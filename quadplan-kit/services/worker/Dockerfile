FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages packages
COPY services services
RUN uv sync --frozen --no-dev --package quarterly-worker
COPY llm_routing.yaml ./
COPY prompts prompts
ENV PATH="/app/.venv/bin:$PATH"
HEALTHCHECK --interval=5s --timeout=5s --retries=20 CMD arq worker.main.WorkerSettings --check
CMD ["arq", "worker.main.WorkerSettings"]
