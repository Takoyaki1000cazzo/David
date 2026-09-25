# David アーキテクチャ

```mermaid
flowchart TB
    subgraph Users["利用者"]
        Child["子ども\nタブレット等のブラウザ"]
        Parent["保護者・先生\nPCブラウザ"]
    end

    subgraph Compose["Docker Compose"]
        Nginx["nginx :80\n静的・メディア配信\nアプリへ委譲"]
        Web["web\nDjango :8000\nbooks 一覧・詳細 / admin"]
        DB[("db\nMySQL 8.4 :3306\ndavid DB")]
    end

    subgraph Browser["ブラウザ内"]
        TTS["Web Speech API\n読み上げ・速度・リピート"]
    end

    Env[".env\n秘密鍵・DB接続情報"]
    Media[("media/\n表紙・ページ画像")]

    Child -->|一覧・詳細・読み上げ\nhttp://host:8000 開発\nhttp://host/ 本番| Nginx
    Parent -->|絵本登録・管理\nhttp://host:8000/admin| Web
    Nginx -->|/ 以外は転送| Web
    Nginx -->|/static/・/media/ 直接配信| StaticMedia["staticfiles・media/"]
    Web -->|SQL 3306\nHOST=db| DB
    Web -->|画像配信 /media| Media
    Web -.->|設定読込| Env
    Child -.->|音声合成| TTS
```

## 構成要素

| 要素 | 役割 |
|---|---|
| `web`（Django） | 絵本一覧 `/`、詳細 `/books/<id>/`、管理 `/admin/`、読み上げUI配信。開発はrunserver、本番はgunicorn（`compose.prod.yaml` で切替） |
| `nginx` | 入口（:80）。`/static/`・`/media/` を直接配信し、アプリ処理のみ `web:8000` へ転送 |
| `db`（MySQL 8.4） | `Book`・`Page`・認証等の永続化（`david` DB） |
| `media/` | 表紙（`covers/`）・ページ画像（`pages/`）の保存・配信 |
| Web Speech API | ブラウザ標準の英文読み上げ（速度・リピート・日訳表示切替） |
| `.env` | `DJANGO_SECRET_KEY`・DB接続情報をホストとコンテナで共有（Git管理外） |

## データの流れ

1. 保護者が `/admin/` で絵本・ページ（日英テキスト・画像）を登録 → `db` に保存
2. 子どもが `/` で絵本を選択 → `/books/<id>/` で本文・画像を表示
3. 「よみあげる」ボタン → ブラウザのWeb Speech APIが英文を音声再生

## ポート

| 公開 | 用途 |
|---|---|
| `8000` | web直結（開発用） |
| `80` | nginx経由（静的配信あり・本番想定） |
| `3306` | db（ホストからの直接接続・管理用） |

## 開発時の別形態

ホスト直実行も可能：ホストの `runserver` ＋ `MYSQL_HOST=127.0.0.1` で、PC上のMySQL（`.env` の `MYSQL_PORT`）に接続する。
コンテナ実行時は `MYSQL_HOST=db` が優先され、コンテナ間接続になる。
