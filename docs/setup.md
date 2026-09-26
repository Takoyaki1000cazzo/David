# 開発環境セットアップ手順書

OS別の準備が済んだら、下の共通手順に進んでください。
所要時間の目安：15〜30分（初回・MySQLありの場合）。

## 0. OS別の準備（どれか1つ）

- Windows（WSL2 + Ubuntu）：[WSL2での準備](setup-wsl2.md)
- macOS：[macOSでの準備](setup-mac.md)
- Linux（Ubuntu / Debian系）：[Linuxでの準備](setup-linux.md)

ここでは Python・MySQL（またはDocker）・ビルド用ツールを入れます。
セットアップ後の開発の流れは [PRを出す前の確認リスト](pr-checklist.md) を参照してください。

## 1. リポジトリを取得

```bash
git clone git@github.com:Takoyaki1000cazzo/David.git
cd David
git checkout main
git pull origin main
```

SSH鍵を登録していない場合は、HTTPSでも取得できます：

```bash
git clone https://github.com/Takoyaki1000cazzo/David.git
```

## 2. `.env` を作る

```bash
cp .env.example .env
```

`.env` の `DJANGO_SECRET_KEY` をランダムな文字列に置き換えてください。
生成コマンド例：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

`.env` の実値はコミットしないでください（`.gitignore` 済み）。

## 3. DBを起動する（Docker Compose・標準）

```bash
docker compose up -d
```

`.env` の `MYSQL_*`（DB名・ユーザー・パスワード）がそのまま使われます。
デフォルトでは `127.0.0.1:3306` に `david` DBができます。
DBの起動には少し時間がかかるので、`docker compose ps` で `running` を確認してから次へ進んでください。

### Dockerを使わない場合

OSに直接入れたMySQLを使う場合は、`david` DBとユーザーを手動作成し、`.env` の `MYSQL_*` と合わせてください。作成例：

```sql
CREATE DATABASE IF NOT EXISTS david CHARACTER SET utf8mb4;
CREATE USER IF NOT EXISTS 'david'@'localhost' IDENTIFIED BY 'changeme';
GRANT ALL PRIVILEGES ON david.* TO 'david'@'localhost';
FLUSH PRIVILEGES;
```

## 4. 仮想環境＋依存インストール

Python 3.10以上が必要です。まず版を確認してください：

```bash
python3 --version
```

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

有効化できるとプロンプトの先頭に `(.venv)` と付きます。

内容：Django、mysqlclient、python-dotenv、Pillow。

## 5. マイグレーション

```bash
python manage.py check
python manage.py migrate
```

## 6. サンプルデータ投入（任意）

```bash
python manage.py loaddata free_books_seed sample_users sample_favorites sample_progress
```

絵本10件（各3ページ）＋ユーザー・お気に入り・進捗のサンプルが入ります。

## 7. 管理ユーザ作成（任意・adminを使う場合）

```bash
python manage.py createsuperuser
```

## 8. 起動

```bash
python manage.py runserver
```

- 一覧：http://127.0.0.1:8000/
- 管理画面：http://127.0.0.1:8000/admin/

## 9. テスト実行

```bash
python manage.py test
```

PRを出す前に必ず実行し、結果をPR本文の「動作確認」に記載してください。

## 動作確認の目安

- `http://127.0.0.1:8000/` が200を返す
- `http://127.0.0.1:8000/admin/` が200を返す
- `python manage.py test` がexit 0

## トラブルシューティング

| 症状 | 対処 |
|---|---|
| `Access denied for user 'david'` | DB・ユーザーが未作成。手順3を見直す。Docker未使用の場合は手動で `CREATE DATABASE david`＋ユーザー作成が必要 |
| `Can't connect to MySQL server` | DBが起動していない。`docker compose ps` で確認 |
| `mysqlclient` のインストール失敗 | MySQL開発用ライブラリ不足。OS別ページのビルドツール導入を見直す |
| `Pillow is not installed` | `pip install -r requirements.txt` を再実行 |
| ポート3306が使用中 | 既存MySQLと競合。どちらかを止めるか、別ポートのMySQLを用意して `.env` の `MYSQL_PORT` を変える |

## 10. 次へ：開発開始

セットアップ完了後の毎日の始め方は以下です。

```bash
docker compose up -d
source .venv/bin/activate
python manage.py runserver
```

開発の進め方・PRの出し方は [PRを出す前の確認リスト](pr-checklist.md) を見てください。

---
検証：2026-09-15・Windows (Git Bash)＋MySQL 8.4で共通手順を検証（Docker手順は未検証）
