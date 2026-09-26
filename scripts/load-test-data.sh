#!/usr/bin/env bash
# 開発・動作確認用テストデータの投入（参照順に注意）
# 使い方: bash scripts/load-test-data.sh [--reset]
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -x ".venv/Scripts/python.exe" ]; then
  PY=".venv/Scripts/python.exe"
elif [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="python3"
fi

if [ "${1:-}" = "--reset" ]; then
  echo "flushing database..."
  "$PY" manage.py flush --noinput
fi

echo "loading fixtures..."
"$PY" manage.py loaddata sample_users free_books_seed sample_progress sample_favorites
echo "done."
