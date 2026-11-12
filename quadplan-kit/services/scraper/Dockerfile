FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages packages
COPY services services
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 && rm -rf /var/lib/apt/lists/* \
 && uv sync --frozen --no-dev --package quarterly-scraper \
 && /app/.venv/bin/playwright install --with-deps chromium
ENV PATH="/app/.venv/bin:$PATH"
HEALTHCHECK --interval=5s --timeout=3s --retries=30 CMD test -s /tmp/scraper-healthy
CMD ["python", "-m", "scraper.main"]
