#!/usr/bin/env bash
# Restore an archive made by backup_volume.sh into the running stack, then restart it.
# Existing files with the same names are overwritten; others are left alone.
#   bash scripts/restore_volume.sh backups/argus-data-....tar.gz
set -euo pipefail
cd "$(dirname "$0")/.."
FILE="${1:?usage: restore_volume.sh ARCHIVE}"
COMPOSE="${ARGUS_COMPOSE:-docker compose}"
[[ -f "$FILE" ]] || { echo "no such file: $FILE" >&2; exit 1; }
if tar tzf "$FILE" | grep -Eq '(^/|(^|/)\.\.(/|$))'; then
    echo "refusing an archive with absolute or parent paths" >&2
    exit 1
fi
# shellcheck disable=SC2086
$COMPOSE exec -T argus tar xzf - -C /app/artifacts < "$FILE"
# shellcheck disable=SC2086
$COMPOSE restart argus
echo "restored: $FILE"
