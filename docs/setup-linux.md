# Linux（Ubuntu / Debian系）での準備

## 1. 基本ツールを導入

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip pkg-config build-essential python3-dev default-libmysqlclient-dev
```

- `python3-venv`：仮想環境用（必須）
- `default-libmysqlclient-dev`＋`pkg-config`：`mysqlclient` のビルド用（必須）

## 2. MySQLを用意（どちらか）

### A. Docker Composeで立てる（推奨・手順書どおり）

Docker Engine＋Compose pluginをインストールします（[公式手順](https://docs.docker.com/engine/install/)）：

```bash
docker compose version
```

### B. OSのMySQLを直接使う

```bash
sudo apt install -y mysql-server
sudo systemctl enable --now mysql
```

その後は [setup.md の「Dockerを使わない場合」](setup.md#dockerを使わない場合) の手順でDB・ユーザーを作成してください。

## 3. 次へ：共通手順へ

[setup.md](setup.md) の「1. リポジトリを取得」から共通手順に進んでください。
共通手順が終われば開発開始です。日々の開発の始め方は setup.md の末尾「10. 次へ：開発開始」を見てください。

## 注意点

- `python` ではなく `python3` コマンドを使ってください
- ファイアウォール等で3306番を塞いでいる場合は開放・変更してください

---
検証：2026-09-15作成・Linux実機では未検証（要検証）
