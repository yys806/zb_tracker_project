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
    "$HOME/下载"/tracker_project*.zip \
    "$HOME/Downloads"/tracker_project*.zip \
    "$HOME"/v*.zip; do
    if [ -f "$candidate" ]; then
      ZIP_PATH="$candidate"
      break
    fi
  done
fi

if [ -z "$ZIP_PATH" ] || [ ! -f "$ZIP_PATH" ]; then
  echo "[00] 没找到压缩包，请用 --zip 指定路径"
  exit 1
fi

PARENT_DIR="$(dirname "$TARGET_DIR")"
TARGET_NAME="$(basename "$TARGET_DIR")"

mkdir -p "$PARENT_DIR"
cd "$PARENT_DIR"

if [ -d "$TARGET_NAME" ]; then
  if [ "$BACKUP" -eq 1 ]; then
    BACKUP_NAME="${TARGET_NAME}_backup_$(date +%Y%m%d_%H%M%S)"
    echo "[00] 旧项目改名: $BACKUP_NAME"
    mv "$TARGET_NAME" "$BACKUP_NAME"
  else
    echo "[00] 删除旧项目: $TARGET_NAME"
    rm -rf "$TARGET_NAME"
  fi
fi

echo "[00] 解压: $ZIP_PATH"
unzip -o "$ZIP_PATH"

if [ ! -d "$TARGET_NAME" ] && [ -d "tracker_project" ]; then
  mv tracker_project "$TARGET_NAME"
fi

if [ ! -d "$TARGET_DIR" ]; then
  echo "[00] 解压后没有找到目标目录: $TARGET_DIR"
  exit 1
fi

cd "$TARGET_DIR"
echo "[00] 当前目录: $(pwd)"
