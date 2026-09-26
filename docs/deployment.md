# 本番デプロイ手順（Gunicorn + Nginx）

## 1. 構成概要

```text
Client → Nginx(:80) → Gunicorn(127.0.0.1:8000) → Django → MySQL
              ├─ /static/ → <APP_ROOT>/staticfiles/ を直接配信
              └─ /media/  → <APP_ROOT>/media/ を直接配信
```

- 動的リクエスト（HTML・API・`/admin/`）のみ Gunicorn へリバースプロキシする。
- 関連ファイル: `config/settings.py`（`STATIC_ROOT`/`STORAGES`）、`gunicorn.conf.py`、
  `compose.prod.yaml`、`nginx/david.conf`。

## 2. 前提

- `.env` に本番値を設定する（`.env.example` 参照）。
  - `DEBUG=False`
  - `DJANGO_SECRET_KEY`（ランダム文字列）
  - `ALLOWED_HOSTS`（公開ホスト名。未設定だと compose.prod が起動時にエラーで止める）
  - `MYSQL_*`（DB 接続情報）
- `requirements.txt`（`gunicorn`・`whitenoise` 含む）をインストール済みであること。

## 3. 手順A: ホストに直接配置する場合

```bash
# 1. マイグレーション
python manage.py migrate

# 2. 静的ファイル集約（Django管理画面などのCSS/JSを staticfiles/ に集める）
python manage.py collectstatic --noinput

# 3. 初期データ（必要に応じて）
python manage.py loaddata free_books_seed sample_users sample_favorites sample_progress

# 4. Gunicorn 起動（設定は gunicorn.conf.py: bind 0.0.0.0:8000, workers 3）
gunicorn config.wsgi:application -c gunicorn.conf.py

# 5. Nginx 設定を配置（<APP_ROOT> と <SERVER_NAME> を置換）
sed -e "s|<APP_ROOT>|/srv/david|g" -e "s|<SERVER_NAME>|ehon.example.com|g" \
  nginx/david.conf | sudo tee /etc/nginx/sites-available/david
sudo ln -s /etc/nginx/sites-available/david /etc/nginx/sites-enabled/david
sudo nginx -t && sudo systemctl reload nginx
```

## 4. 手順B: Docker Compose で起動する場合

```bash
# .env の ALLOWED_HOSTS 設定が必須
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

`compose.prod.yaml` は起動時に `migrate → collectstatic → gunicorn` を自動実行する。
Nginx を別途ホスト（またはリバースプロキシ用コンテナ）に置き、
`proxy_pass http://<webホスト>:8000` へ向ける（テンプレは同一ホスト想定）。

## 5. 動作確認

```bash
# 動的ページ（Gunicorn 経由）
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/books/10/

# 静的ファイル（本番は Nginx が配信。Django直でも200になること）
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/static/admin/css/base.css

# ALLOWED_HOSTS  enforcement（想定: 400）
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/ -H "Host: evil.example.com"

# Nginx 越し（公開ホスト名で）
curl -s -o /dev/null -w "%{http_code}\n" http://ehon.example.com/
curl -s -o /dev/null -w "%{http_code}\n" http://ehon.example.com/static/admin/css/base.css
```

## 6. トラブルシューティング

| 症状 | 原因・対処 |
| --- | --- |
| 全ページ 400 | `ALLOWED_HOSTS` 未設定。`.env` に公開ホスト名を追加し再起動 |
| `/static/` が 404（Nginx） | `collectstatic` 未実行、または `alias` 行末の `/` 漏れ・`<APP_ROOT>` 置換ミス |
| `/media/` の画像が出ない | `media/` への Nginx 実行ユーザーの読み取り権限不足。`chmod -R o+rX media staticfiles` 等で付与 |
| アップロードが 413 | `client_max_body_size` 不足。テンプレは 10m（アプリ上限 5MB 対応） |
| 起動が重い・タイムアウト | `gunicorn.conf.py` の `workers`/`timeout` を調整（目安: `2 × CPU + 1`） |
