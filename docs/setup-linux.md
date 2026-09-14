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

## 3. 次へ

[docs/setup.md](setup.md) の「1. リポジトリを取得」に進んでください。

## 注意点

- `python` ではなく `python3` コマンドを使ってください
- ファイアウォール等で3306番を塞いでいる場合は開放・変更してください
