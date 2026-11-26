# Deploying Quarterly on one VM

The full stack runs with Docker Compose on one small Linux VM:

- 2-4 vCPUs
- 4-8 GB RAM
- 40 GB disk

Caddy terminates TLS. Caddy is the only part that the internet can reach.

## 1. Prepare the VM

1. Create the VM (Ubuntu 24.04 LTS).
2. Point the DNS `A` record of the domain at the VM.
3. Do not add an `AAAA` (IPv6) record for now. The reason:
   - The Docker network of the stack is IPv4 only.
   - Thus Docker would send every IPv6 visitor to Caddy from one internal address.
   - All these visitors would then share one set of rate limits.
4. To add IPv6 at a later time, do these steps:
   1. Enable IPv6 on the network in `deploy/docker-compose.prod.yml` (`networks: default: enable_ipv6: true` with an `fd00::/64`-style subnet).
   2. Connect with `curl -6`. At the same time, run `docker compose exec caddy netstat -tn`.
   3. Make sure that the peer is your own IPv6 address, not `172.x.0.1`.
5. Install Docker Engine and the Compose plugin (`https://docs.docker.com/engine/install/ubuntu/`).
6. Make sure that `openssl` is installed (it is already present).
7. Optional: Install the MinIO client `mc` for off-site backups.
8. Open only ports 80 and 443 (`ufw allow 80,443/tcp`), and SSH.
9. Clone the repository.
10. Go into the repository folder with `cd`.

## 2. Production settings (`.env`)

Copy `.env.example` to `.env`. Then change the settings in the table below.

With `ENVIRONMENT=production`, the API does not start if a development value stays. These are the development values:

- Development secrets.
- `EMAIL_BACKEND=console`.
- `SESSION_COOKIE_SECURE=false`.

| Setting | Production value |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `SERVER_HMAC_KEY`, `ISSUANCE_HMAC_KEY`, `SESSION_SECRET` | A new random value for each: `openssl rand -base64 48`. If you lose `SERVER_HMAC_KEY`, every pseudonym link breaks. Thus, keep a separate backup of this key (not in the database backup). |
| `POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD` | New random values. Change `DATABASE_URL` to agree with them. |
| `EMAIL_BACKEND` | `smtp`, with the `SMTP_*` settings of the mail provider. |
| `SESSION_COOKIE_SECURE` | `true` (the default). |
| `SHOW_UNPUBLISHED_PROGRAMS` | `false`. Students see only the programs that a curator published in `/admin/review`. |
| `LLM_LIVE` | `false` until Richard approves API spend. After his approval, `true` with `ANTHROPIC_API_KEY` (and `OPENROUTER_API_KEY` for the fallback). |
| `LLM_SPEND_ALARM_USD` | The daily spend that starts the alarm (default 5). |
| `CATALOG_INGEST_ENABLED`, `SCHEDULE_SCRAPER_ENABLED` | `false`. The schedule scraper stays off until the University gives written permission. |
| `QUARTERLY_DOMAIN` | The domain of the site, for Caddy. |
| `COMPOSE_FILE` | `docker-compose.yml:deploy/docker-compose.prod.yml`. With this value, every `docker compose` command (and `make up`) on the server uses the production settings. Without this value, `make up` would publish the database, Redis, MinIO and the API. It publishes them on 127.0.0.1 only, but without the production checks. Never run `make e2e` on the server. |

Write each value as `NAME=value`. Do not put a space after `=`.

## 3. Start

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build --wait
docker compose exec api alembic upgrade head        # also runs at API start-up
docker compose exec api python -m api.cli seed      # the hand-checked catalog seed
```

Then, as an admin, publish each program in `/admin/review`.

To make the first admin, run this command:

`docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "UPDATE account SET role='admin' WHERE username='<name>';"`

`deploy/docker-compose.prod.yml` does these things:

- It sets `ENVIRONMENT=production` for the API and the worker.
- It sets `TRUSTED_PROXY_HOPS=2`. Caddy and nginx both append to `X-Forwarded-For`. With this value, the rate limits see the real address of each visitor. With only nginx in front (as in development), the value is 1.
- It adds Caddy (`deploy/Caddyfile`). Caddy gives automatic TLS and HSTS, and it keeps no access log. The Caddy log keeps no IP addresses and no request headers.
- It stops the publication of the database, Redis, MinIO and the API on the host.

The API runs 4 worker processes (`WEB_CONCURRENCY`).

## 4. Backups

`scripts/backup.sh` does these things:

1. It dumps Postgres.
2. It encrypts the dump (AES-256, with a key from a passphrase file) and adds a checksum.
3. It keeps the backups of 14 days.

Install the script as a nightly cron job:

```bash
openssl rand -base64 48 > /root/quarterly-backup.pass && chmod 600 /root/quarterly-backup.pass
crontab -e
# 15 3 * * * cd /srv/quarterly && BACKUP_PASSPHRASE_FILE=/root/quarterly-backup.pass BACKUP_S3_TARGET=offsite/quarterly-backups scripts/backup.sh >> /var/log/quarterly-backup.log 2>&1
```

Keep a copy of the passphrase in a location that is not the VM.

Give the off-site bucket the same 14-day limit. Then the emails of deleted accounts do not stay there: `mc ilm rule add --expire-days 14 offsite/quarterly-backups`.

Test a restore every few months:

```bash
docker compose stop api worker
BACKUP_PASSPHRASE_FILE=/root/quarterly-backup.pass scripts/restore.sh backups/quarterly-YYYY-MM-DD.dump.enc
docker compose start api worker
```

A restore brings back the accounts that users deleted after the backup (with their emails). Thus:

- Restore only to recover from the loss of the database.
- After a restore, ask each person who deleted their account in that period to delete it again (`docs/OPEN_QUESTIONS.md` P12-3).

## 5. Monitoring

- `docker compose ps` shows the health of the services.
- `curl https://<domain>/api/health` returns `{"status":"ok","db":true,"redis":true}`.
- The worker checks the model spend of the day (`llm_call`) every hour. When the spend is more than `LLM_SPEND_ALARM_USD`, the worker logs `LLM SPEND ALARM`. To find the alarm, run `docker compose logs worker | grep "SPEND ALARM"`.
- Logs never contain email addresses or IP addresses. The API and the worker redact them. Caddy and nginx keep no access log.

## 6. Updating

Before you update, make a backup (`scripts/backup.sh`). Then run:

```bash
git pull
docker compose -f docker-compose.yml -f deploy/docker-compose.prod.yml up -d --build --wait
```

Migrations run when the API starts.
