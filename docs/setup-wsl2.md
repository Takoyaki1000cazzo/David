# WSL2（Windows + Ubuntu）での準備

Windows本体ではなく、WSL2上のUbuntuに環境を作ります。
ファイルもUbuntu側（`~/` 配下）に置くのが高速で安定します。

## 1. WSL2 + Ubuntuを有効化（未導入の場合）

管理者権限のPowerShellで：

```powershell
wsl --install -d Ubuntu
```

再起動後、Ubuntuを起動してユーザー作成を済ませてください。

## 2. 基本ツールを導入（Ubuntu側）

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip pkg-config build-essential python3-dev default-libmysqlclient-dev
```

- `python3-venv`：仮想環境用（必須）
- `default-libmysqlclient-dev`＋`pkg-config`：`mysqlclient` のビルド用（必須）

## 3. Docker Desktopを連携（推奨）

1. Windows側にDocker Desktopをインストール
2. Settings → Resources → WSL Integration でUbuntuをON
3. Ubuntu側で確認：

```bash
docker compose version
```

Dockerを使わない場合は、Ubuntu側にMySQLを直接入れる手もあります：

```bash
sudo apt install -y mysql-server
sudo systemctl enable --now mysql
```

その場合は [setup.md の「Dockerを使わない場合」](setup.md#dockerを使わない場合) の手順でDB・ユーザーを作成してください。

## 4. 次へ

[docs/setup.md](setup.md) の「1. リポジトリを取得」に進んでください。
以降のコマンドはすべてUbuntu側で実行します。

## 注意点

- ブラウザ確認はWindows側のブラウザで `http://localhost:8000` を開けます
- リポジトリを `/mnt/c/` 配下（Windows側）に置くと激重になるので `~/David` 等に置くこと
- `python` ではなく `python3` コマンドを使ってください
