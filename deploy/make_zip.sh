#!/usr/bin/env bash
# ------------------------------------------------------------------
# Build a single deliverable zip of the Jaguar AI project.
# Excludes venvs, caches, runtime data, and large media so the
# archive stays small and there's nothing sensitive inside it.
# ------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="${OUT:-$ROOT/jaguar_ai.zip}"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/jaguar_ai"

# Use rsync if available for clean excludes; otherwise tar+zip.
if command -v rsync >/dev/null 2>&1; then
  rsync -a \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' \
    --exclude='.git' --exclude='.idea' --exclude='.vscode' \
    --exclude='myenv' --exclude='venv' --exclude='.venv' --exclude='env' \
    --exclude='jaguar_data' --exclude='uploads' --exclude='logs' \
    --exclude='*.sqlite3' --exclude='*.index' \
    --exclude='.env' --exclude='*.env.local' \
    --exclude='back.png' --exclude='logo1.png' \
    --exclude='*.mp3' --exclude='*.mp4' --exclude='*.wav' \
    --exclude='.DS_Store' --exclude='Thumbs.db' \
    ./ "$STAGE/jaguar_ai/"
else
  tar --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' \
      --exclude='.git' --exclude='.idea' --exclude='.vscode' \
      --exclude='myenv' --exclude='venv' --exclude='.venv' --exclude='env' \
      --exclude='jaguar_data' --exclude='uploads' --exclude='logs' \
      --exclude='.env' \
      -cf - . | (cd "$STAGE" && tar -xf -)
  # rsync fallback leaves everything in $STAGE; move into the wrapper dir.
  rm -rf "$STAGE/jaguar_ai"
  mv "$STAGE"/*/ "$STAGE/jaguar_ai"/ 2>/dev/null || mv "$STAGE"/. "$STAGE/jaguar_ai"/ || true
  mkdir -p "$STAGE/jaguar_ai"
  shopt -s dotglob
  mv "$STAGE"/* "$STAGE/jaguar_ai/" 2>/dev/null || true
fi

# Build the zip
if command -v zip >/dev/null 2>&1; then
  (cd "$STAGE" && zip -qr "$OUT" jaguar_ai)
else
  (cd "$STAGE" && python -m zipfile -c "$OUT" jaguar_ai)
fi

echo "Wrote $OUT ($(du -h "$OUT" | cut -f1))"
