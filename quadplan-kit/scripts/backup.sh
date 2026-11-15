#!/usr/bin/env bash
# Nightly encrypted Postgres backup (prompt 12). Run from the quadplan-kit folder on the server:
#
#   BACKUP_PASSPHRASE_FILE=/root/quarterly-backup.pass scripts/backup.sh
#
# Writes backups/quarterly-<YYYY-MM-DD>.dump.enc (a pg_dump custom-format archive, encrypted
# with AES-256 by openssl, key derived with PBKDF2 from the passphrase in BACKUP_PASSPHRASE_FILE)
# and a .sha256 checksum beside it, keeps the last
# BACKUP_KEEP_DAYS days (default 14), and, if BACKUP_S3_TARGET is set (for example
# "minio/quarterly-backups"), copies the file there with the MinIO client `mc`.
# The dump holds account emails: never store it unencrypted, and keep the passphrase off the
# server's backup target. Restore with scripts/restore.sh.
set -euo pipefail

cd "$(dirname "$0")/.."
: "${BACKUP_PASSPHRASE_FILE:?set BACKUP_PASSPHRASE_FILE to a file holding the passphrase}"
[ -r "$BACKUP_PASSPHRASE_FILE" ] || { echo "backup: cannot read $BACKUP_PASSPHRASE_FILE" >&2; exit 1; }
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
OUT_DIR="${BACKUP_DIR:-backups}"
mkdir -p "$OUT_DIR"
chmod 700 "$OUT_DIR"
day="$(date -u +%F)"
out="$OUT_DIR/quarterly-$day.dump.enc"

# Read the database name and user from the running container, never from the command line.
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner' \
  | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 -pass "file:$BACKUP_PASSPHRASE_FILE" -out "$out"
chmod 600 "$out"
(cd "$OUT_DIR" && shasum -a 256 "$(basename "$out")" > "$(basename "$out").sha256")
size=$(wc -c < "$out" | tr -d ' ')
[ "$size" -gt 1024 ] || { echo "backup: $out is suspiciously small ($size bytes)" >&2; exit 1; }

find "$OUT_DIR" -name 'quarterly-*.dump.enc*' -mtime +"$KEEP_DAYS" -delete
if [ -n "${BACKUP_S3_TARGET:-}" ]; then
  mc cp --quiet "$out" "$out.sha256" "$BACKUP_S3_TARGET/"
fi
echo "backup: wrote $out ($size bytes)"
