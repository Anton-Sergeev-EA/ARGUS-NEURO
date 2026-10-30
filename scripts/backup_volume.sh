#!/usr/bin/env bash
# Archive the data volume (models, public datasets, saved reports) of the running stack.
#   bash scripts/backup_volume.sh [file.tar.gz]
# Use ARGUS_COMPOSE for another stack, e.g.
#   ARGUS_COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env"
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE="${ARGUS_COMPOSE:-docker compose}"
OUT="${1:-backups/argus-data-$(date -u +%Y%m%dT%H%M%SZ).tar.gz}"
mkdir -p "$(dirname "$OUT")"
# shellcheck disable=SC2086
$COMPOSE exec -T argus tar czf - -C /app/artifacts . > "$OUT.part"
tar tzf "$OUT.part" > /dev/null   # refuse to keep an archive that cannot be read back
mv "$OUT.part" "$OUT"
echo "backup written: $OUT ($(du -h "$OUT" | cut -f1))"
