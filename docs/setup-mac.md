# macOSでの準備

Homebrewを使って必要なソフトを入れます。

## 1. Homebrew（未導入の場合）

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

## 2. Python・Git・ビルド用ツールを導入

```bash
brew install git python mysql-client pkg-config
```

- `mysql-client`＋`pkg-config`：`mysqlclient` のビルド用（必須）
- インストール後にPATHを通します（Apple Siliconの例）：

```bash
echo 'export PATH="/opt/homebrew/opt/mysql-client/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
which mysql_config
```

Intel Macの場合は `/opt/homebrew` を `/usr/local` に読み替えてください。

## 3. MySQLを用意（どちらか）

### A. Dockerで立てる（推奨・手順書どおり）

Docker DesktopまたはOrbStackをインストールし：

```bash
docker compose version
```

### B. HomebrewのMySQLを直接使う

```bash
brew install mysql
brew services start mysql
```

※ 8.x系が入ります。その後は [setup.md の「Dockerを使わない場合」](setup.md#dockerを使わない場合) の手順でDB・ユーザーを作成してください。

## 4. 次へ

[docs/setup.md](setup.md) の「1. リポジトリを取得」に進んでください。

## 注意点

- `mysqlclient` 導入前に `mysql_config` が見つかることを確認してください（`which mysql_config`）。venvの作り方は共通手順の「4. 仮想環境＋依存インストール」を見てください
