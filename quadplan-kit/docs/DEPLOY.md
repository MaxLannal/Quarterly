# Deploying Quarterly on one VM

The whole stack runs with Docker Compose on a single small Linux VM (2-4 vCPUs, 4-8 GB RAM, 40 GB disk). Caddy terminates TLS and is the only thing reachable from the internet.

## 1. Prepare the VM

1. Create the VM (Ubuntu 24.04 LTS) and point the domain's DNS `A`/`AAAA` records at it.
2. Install Docker Engine and the Compose plugin (`https://docs.docker.com/engine/install/ubuntu/`), plus `openssl` (already present) and, optionally, the MinIO client `mc` for off-site backups.
3. Open ports 80 and 443 only (`ufw allow 80,443/tcp`), plus SSH.
4. Clone the repository and `cd quadplan-kit`.

## 2. Production settings (`.env`)

Copy `.env.example` to `.env` and change these. With `ENVIRONMENT=production` the API refuses to start while any development value is left (development secrets, `EMAIL_BACKEND=console`, `SESSION_COOKIE_SECURE=false`).

| Setting | Production value |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `SERVER_HMAC_KEY`, `ISSUANCE_HMAC_KEY`, `SESSION_SECRET` | each a new random value: `openssl rand -base64 48`. Losing `SERVER_HMAC_KEY` breaks every pseudonym link, so back it up separately (not in the database backup). |
| `POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD` | new random values; update `DATABASE_URL` to match |
| `EMAIL_BACKEND` | `smtp`, with the `SMTP_*` settings of the mail provider |
| `SESSION_COOKIE_SECURE` | `true` (the default) |
| `SHOW_UNPUBLISHED_PROGRAMS` | `false`: students see only programs a curator published in `/admin/review` |
| `LLM_LIVE` | `false` until Richard approves API spend; then `true` with `ANTHROPIC_API_KEY` (and `OPENROUTER_API_KEY` for the fallback) |
| `LLM_SPEND_ALARM_USD` | daily spend that raises the alarm (default 5) |
| `CATALOG_INGEST_ENABLED`, `SCHEDULE_SCRAPER_ENABLED` | `false` (the schedule scraper stays off until the University permits it in writing) |
| `QUARTERLY_DOMAIN` | the site's domain, for Caddy |

Write each value as `NAME=value` with no space after `=`.

## 3. Start

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build --wait
docker compose exec api alembic upgrade head        # also runs at API start-up
docker compose exec api python -m api.cli seed      # the hand-checked catalog seed
```

Then, as an admin, publish each program in `/admin/review` (make the first admin with `docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "UPDATE account SET role='admin' WHERE username='<name>';"`).

`deploy/docker-compose.prod.yml` sets `TRUSTED_PROXY_HOPS=2` (Caddy and nginx both append to `X-Forwarded-For`, so rate limits see each visitor's own address; with only nginx in front, as in development, it is 1) and adds Caddy (`deploy/Caddyfile`: automatic TLS, HSTS, no access log, so no IP addresses are kept) and stops publishing the database, Redis, MinIO and the API on the host. The API runs 4 worker processes (`WEB_CONCURRENCY`).

## 4. Backups

`scripts/backup.sh` dumps Postgres, encrypts it (AES-256, key from a passphrase file) with a checksum, and keeps 14 days. Install it as a nightly cron job:

```bash
openssl rand -base64 48 > /root/quarterly-backup.pass && chmod 600 /root/quarterly-backup.pass
crontab -e
# 15 3 * * * cd /srv/quarterly/quadplan-kit && BACKUP_PASSPHRASE_FILE=/root/quarterly-backup.pass BACKUP_S3_TARGET=offsite/quarterly-backups scripts/backup.sh >> /var/log/quarterly-backup.log 2>&1
```

Keep a copy of the passphrase somewhere other than the VM. Test a restore every few months:

```bash
docker compose stop api worker
BACKUP_PASSPHRASE_FILE=/root/quarterly-backup.pass scripts/restore.sh backups/quarterly-YYYY-MM-DD.dump.enc
docker compose start api worker
```

## 5. Monitoring

- `docker compose ps` shows health; `curl https://<domain>/api/health` returns `{"status":"ok","db":true,"redis":true}`.
- The worker checks the day's model spend (`llm_call`) every hour and logs `LLM SPEND ALARM` when it passes `LLM_SPEND_ALARM_USD`; `docker compose logs worker | grep "SPEND ALARM"`.
- Logs never contain email or IP addresses (redaction is on in the API and the worker; Caddy and nginx keep no access log).

## 6. Updating

```bash
git pull
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build --wait
```

Migrations run when the API starts. Take a backup first (`scripts/backup.sh`).
