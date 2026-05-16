#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${ROOT_DIR}/dist"
ARCHIVE_NAME="skills-active-migration-$(date +%Y%m%d)"

usage() {
  cat <<'EOF'
Usage: ./scripts/package-migration.sh [--output-dir PATH] [--name ARCHIVE_NAME] [--include-submodules]

Create a clean migration archive for the active skills repo.

Options:
  --output-dir PATH   Directory that will receive the archive and checksum
  --name NAME         Archive basename without extension
  --include-submodules
                      Include optional submodule working trees such as multi-search
  --help              Show this help text
EOF
}

INCLUDE_SUBMODULES="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --name)
      ARCHIVE_NAME="$2"
      shift 2
      ;;
    --include-submodules)
      INCLUDE_SUBMODULES="true"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

mkdir -p "$OUTPUT_DIR"

ARCHIVE_PATH="${OUTPUT_DIR}/${ARCHIVE_NAME}.tar.gz"
CHECKSUM_PATH="${ARCHIVE_PATH}.sha256"
PARENT_DIR="$(dirname "$ROOT_DIR")"
ROOT_NAME="$(basename "$ROOT_DIR")"

TAR_EXCLUDES=(
  --exclude='*/.git'
  --exclude='*/.git/*'
  --exclude='*/.DS_Store'
  --exclude='*/__pycache__'
  --exclude='*/__pycache__/*'
  --exclude='*.pyc'
  --exclude='*.pyo'
  --exclude='*/dist'
  --exclude='*/dist/*'
  --exclude='*/.env'
  --exclude='*/.env.local'
  --exclude='*/.env.*.local'
  --exclude='*/.venv'
  --exclude='*/.venv/*'
  --exclude='*/node_modules'
  --exclude='*/node_modules/*'
  --exclude='*/responses'
  --exclude='*/responses/*'
  --exclude='*/downloads'
  --exclude='*/downloads/*'
  --exclude='*/doctor-report*.json'
)

if [[ "$INCLUDE_SUBMODULES" != "true" ]]; then
  TAR_EXCLUDES+=(--exclude="${ROOT_NAME}/skills/meta/multi-search")
  TAR_EXCLUDES+=(--exclude="${ROOT_NAME}/skills/meta/multi-search/*")
fi

tar -czf "$ARCHIVE_PATH" \
  "${TAR_EXCLUDES[@]}" \
  -C "$PARENT_DIR" \
  "$ROOT_NAME"

shasum -a 256 "$ARCHIVE_PATH" > "$CHECKSUM_PATH"

echo "Archive created: $ARCHIVE_PATH"
echo "Checksum written: $CHECKSUM_PATH"
