#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${TARGET_DIR:-$HOME/zb/tracker_project}"
ZIP_PATH=""
BACKUP=1

while [ $# -gt 0 ]; do
  case "$1" in
    --zip)
      ZIP_PATH="${2:-}"
      shift 2
      ;;
    --target-dir)
      TARGET_DIR="${2:-$TARGET_DIR}"
      shift 2
      ;;
    --no-backup)
      BACKUP=0
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

if [ -z "$ZIP_PATH" ]; then
  for candidate in \
    "$HOME/下载"/v*.zip \
    "$HOME/Downloads"/v*.zip \
    "$HOME/Download"/v*.zip \
    "$HOME"/v*.zip \
    "$HOME/下载"/tracker_project*.zip \
    "$HOME/Downloads"/tracker_project*.zip \
    "$HOME/Download"/tracker_project*.zip \
    "$HOME"/tracker_project*.zip; do
    if [ -f "$candidate" ]; then
      ZIP_PATH="$candidate"
      break
    fi
  done
fi

if [ -z "$ZIP_PATH" ] || [ ! -f "$ZIP_PATH" ]; then
  echo "[00] package not found; pass it with --zip /path/to/v28.zip"
  exit 1
fi

PARENT_DIR="$(dirname "$TARGET_DIR")"
TARGET_NAME="$(basename "$TARGET_DIR")"

mkdir -p "$PARENT_DIR"
cd "$PARENT_DIR"

if [ -d "$TARGET_NAME" ]; then
  if [ "$BACKUP" -eq 1 ]; then
    BACKUP_NAME="${TARGET_NAME}_backup_$(date +%Y%m%d_%H%M%S)"
    echo "[00] backup old project as: $BACKUP_NAME"
    mv "$TARGET_NAME" "$BACKUP_NAME"
  else
    echo "[00] remove old project: $TARGET_NAME"
    rm -rf "$TARGET_NAME"
  fi
fi

echo "[00] unzip: $ZIP_PATH"
unzip -o "$ZIP_PATH"

if [ ! -d "$TARGET_NAME" ] && [ -d "tracker_project" ]; then
  mv tracker_project "$TARGET_NAME"
fi

if [ ! -d "$TARGET_DIR" ]; then
  echo "[00] target project directory not found after unzip: $TARGET_DIR"
  exit 1
fi

cd "$TARGET_DIR"
echo "[00] project directory: $(pwd)"

echo "[00] repair Linux permissions"
find "$TARGET_DIR" -type d -exec chmod 755 {} +
find "$TARGET_DIR" -type f -exec chmod 644 {} +
if [ -d "$TARGET_DIR/scripts/run" ]; then
  find "$TARGET_DIR/scripts/run" -type f -name "*.sh" -exec chmod 755 {} +
fi

PYTHON_BIN="${PYTHON_BIN:-$HOME/.venvs/zb/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3 || command -v python || true)"
fi

if [ -z "$PYTHON_BIN" ]; then
  echo "[00] python not found; skip import self-check"
else
  echo "[00] import self-check with: $PYTHON_BIN"
  PYTHONPATH="$TARGET_DIR/src" "$PYTHON_BIN" -c "import orangepi_tracker; print('[00] orangepi_tracker import ok')"
fi
