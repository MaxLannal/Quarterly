FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages packages
COPY services services
RUN uv sync --frozen --no-dev --package quarterly-api
COPY data data
# Model routing and the versioned agent prompts (prompt 07).
COPY llm_routing.yaml ./
COPY prompts prompts
ENV PATH="/app/.venv/bin:$PATH"
ARG GIT_SHA=dev
ENV GIT_SHA=$GIT_SHA
WORKDIR /app/services/api
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --retries=20 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)"
CMD ["sh", "-c", "if [ -f alembic.ini ]; then alembic upgrade head; fi && uvicorn api.main:app --host 0.0.0.0 --port 8000 --no-access-log --workers ${WEB_CONCURRENCY:-4}"]
