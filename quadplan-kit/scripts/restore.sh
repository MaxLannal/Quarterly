#!/usr/bin/env bash
# Restore a backup made by scripts/backup.sh into the running db container.
#
#   BACKUP_PASSPHRASE_FILE=/root/quarterly-backup.pass scripts/restore.sh backups/quarterly-2026-11-15.dump.enc
#
# DANGER: replaces the current database contents (pg_restore --clean). Stop the api and worker
# first (`docker compose stop api worker`), then start them again afterwards.
set -euo pipefail

cd "$(dirname "$0")/.."
file="${1:?usage: scripts/restore.sh <backup file>}"
: "${BACKUP_PASSPHRASE_FILE:?set BACKUP_PASSPHRASE_FILE}"
(cd "$(dirname "$file")" && shasum -a 256 -c "$(basename "$file").sha256" >/dev/null) \
  || { echo "restore: checksum mismatch for $file" >&2; exit 1; }
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass "file:$BACKUP_PASSPHRASE_FILE" -in "$file" \
  | docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner'
echo "restore: done from $file"
