#!/usr/bin/env sh
# pg_dump backup script — runs inside the backup container.
# Dumps the batmonai database to /backups/batmonai_YYYYMMDD_HHMMSS.dump
# and removes dumps older than BACKUP_RETAIN files (default 14).

set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETAIN="${BACKUP_RETAIN:-14}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTFILE="${BACKUP_DIR}/batmonai_${TIMESTAMP}.dump"

mkdir -p "${BACKUP_DIR}"

echo "[backup] Starting dump → ${OUTFILE}"
pg_dump \
  --format=custom \
  --compress=9 \
  --no-password \
  --file="${OUTFILE}"

SIZE=$(du -sh "${OUTFILE}" | cut -f1)
echo "[backup] Done. Size: ${SIZE}"

# Prune old dumps — keep the newest $RETAIN files
COUNT=$(ls -1t "${BACKUP_DIR}"/batmonai_*.dump 2>/dev/null | wc -l)
if [ "${COUNT}" -gt "${RETAIN}" ]; then
  ls -1t "${BACKUP_DIR}"/batmonai_*.dump | tail -n "+$((RETAIN + 1))" | xargs rm -f
  echo "[backup] Pruned old dumps (kept ${RETAIN})."
fi
