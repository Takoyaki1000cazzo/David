# テストデータ投入・リセット手順

開発・動作確認用のfixture投入とDB初期化の手順書。

## fixture一覧

| ファイル | 内容 |
|---|---|
| `sample_users` | teacher（staff）・parentの2ユーザー |
| `free_books_seed` | フリー絵本10冊＋ページ30件（画像パス付き） |
| `sample_progress` | 読書進捗2件（絵本pk10・18を参照） |
| `sample_favorites` | お気に入り3件（絵本pk10・11・18を参照） |

## サンプルユーザー

| ユーザー | パスワード | 権限 |
|---|---|---|
| teacher | teacher123 | staff（管理・一括編集可） |
| parent | parent123 | 一般 |

## 投入手順（スクリプト推奨）

```bash
bash scripts/load-test-data.sh
```

参照順（ユーザー・絵本→進捗・お気に入り）を守ること。手動の場合は以下：

```bash
.venv/Scripts/python.exe manage.py loaddata sample_users free_books_seed sample_progress sample_favorites
```

## リセット手順（初期状態に戻す）

```bash
bash scripts/load-test-data.sh --reset
```

## 注意

- `flush` は全データを削除する。各PCのDBごとに実施が必要
- 新規絵本は `status` が `draft` の場合があり、一覧に出ないときは公開状態を確認する
- サンプルパスワードは開発専用。本番データには使わないこと
