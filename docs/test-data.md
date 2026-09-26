# テストデータ投入・リセット手順

開発・動作確認用のfixture投入とDB初期化の手順書。

## fixture一覧

| ファイル | 内容 |
|---|---|
| `sample_users` | teacher（staff）・parentの2ユーザー |
| `free_books_seed` | フリー絵本10冊＋ページ30件 |
| `sample_progress` | 読書進捗2件（絵本pk1・3を参照） |
| `sample_favorites` | お気に入り3件（絵本pk1〜3を参照） |

## 投入手順

```bash
.venv/Scripts/python.exe manage.py loaddata sample_users free_books_seed sample_progress sample_favorites
```

※参照順のため、ユーザー・絵本を先に投入すること。

## リセット手順（初期状態に戻す）

```bash
.venv/Scripts/python.exe manage.py flush --noinput
.venv/Scripts/python.exe manage.py loaddata sample_users free_books_seed sample_progress sample_favorites
```

## 注意

- `flush` は全データを削除する。各PCのDBごとに実施が必要
- 新規絵本は `status` が `draft` の場合があり、一覧に出ないときは公開状態を確認する
- サンプルユーザーのパスワード平文は別途共有が必要
