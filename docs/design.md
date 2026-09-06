# 英語絵本読み聞かせアプリ 基本設計書 v0.3（案）

> 位置づけ: README仕様案 v0.2（確定済み）＋ PR #5 までの実装を土台にした基本設計。議論用たたき台。
> 対象読者: チーム全員（実装・レビュー・Issue 化用）。

## 1. 概要

英語の絵本を Web 上で閲覧し、英文の読み上げができるアプリ。
子どもが「選ぶ → 読む → 聞く」でき、保護者・先生が絵本を登録する。MVP では最低限が動くことを目標にする。

## 2. MVP機能

- 絵本一覧: タイトル・表紙・対象年齢を表示、対象年齢で絞り込み（GET `age`）
- 絵本詳細: ページごとの画像・英文・日本語訳を表示
- ページ送り: `?p=` による前ページ / 次ページ移動
- 英文の読み上げ: Web Speech API（案A）でページ単位に再生、速度変更・リピート付き
- 日本語訳の ON/OFF: チェックボックスで表示切替
- Django Admin による絵本データの登録・編集（Book＋PageInline）

実装: `books/views.py:6`（一覧・絞り込み）、`books/views.py:15`（詳細・ページ送り）、`books/templates/books/book_detail.html:35`（読み上げ UI）。

## 3. 画面構成

- `/` 絵本一覧
  - 年齢入力＋絞り込み／クリア
  - 各絵本 → `/books/<id>/` へのリンク
- `/books/<id>/` 絵本詳細
  - ├─ 前ページ（`?p=`）
  - ├─ 次ページ（`?p=`）
  - ├─ 読み上げ（🔊 よみあげる／⏹ とめる、速度・リピート）
  - └─ 日本語訳 ON/OFF
- `/admin/` 管理用（Book・Page の CRUD）
- `/media/` 画像配信（DEBUG 時のみ、`config/urls.py:28`）

## 4. データ構成

- `Book`（絵本）: `books/models.py:5`
  - id, title, cover_image(`covers/` → `media/covers/`), age_min, age_max（必須）, description, description_ja, created_at
  - `clean()` で age_min <= age_max を検証
- `Page`（ページ）: `books/models.py:26`
  - id, book(FK, related_name=`pages`), page_no, text_en, text_ja, image(`pages/` → `media/pages/`), audio_url(nullable, 将来の案B用), created_at
  - unique(book, page_no)、ordering は page_no 順

```
Book 1冊
  ├─ Page 1（page_no=1）
  ├─ Page 2（page_no=2）
  └─ Page 3（page_no=3）
```

## 5. 使用技術

- Python 3.12 / Django==5.2.17
- MySQL 8.4（docker: `david-mysql`、`compose.yaml` の db のみ使用、Web は各 PC の venv で実行）
- Lib: mysqlclient==2.2.8, python-dotenv==1.2.3, Pillow==11.3.0
- 表示: Django Templates（素の HTML＋inline style、Bootstrap 未使用 — 導入するなら別 Issue で決定）
- 音声: JavaScript Web Speech API（`en-US`、速度 0.5–1.5、リピート）
- Infra(dev): Docker Compose（DB のみ）

## 6. MVPの対象外（v0.3）

- ユーザー登録・ログイン、課金、学習履歴
- 録音・発音採点
- AI 機能、外部 TTS API・外部 API 連携全般（MVP はブラウザ標準の読み上げのみ）
- ネイティブ音声の自前生成基盤（案B: バックエンドで MP3 生成 → `audio_url` 活用は将来対応）

※ v0.2 の対象外（会員・録音・外部 API）を継続し、課金・学習履歴・AI を v0.3 として追記。

## 7. 現状と課題（main 同期済み、PR #5 まで）

1. `books/tests.py:1` が空。`clean()` や unique や view のテストなし。
2. サンプルデータなし。各 PC で表示がバラつく。Fixture（例: `books/fixtures/sample_books.json`）がない。
3. 一覧の年齢絞り込みが Python 側フィルタ（`books/views.py:11`）。DB フィルタ（`age_min__lte` / `age_max__gte`）にすべき。
4. README のロードマップ（`README.md:64`）が未更新。実装済みなのに `[ ]` のまま。
5. `Pillow` は導入済みだが README 技術スタック（`README.md:46`）に記載なし。
6. セットアップ手順が混在 OS（Win WSL2 / Mac / Linux）でブレる。SECRET_KEY 生成・Activate 方法・MySQL 起動待ちがない。

## 8. Issue 化候補（D-1〜D-5）

- D-1: README ロードマップ更新＋Pillow 追記。完了条件: ロードマップが実装済み状態と一致。
- D-2: Fixture 追加＋`loaddata` 手順化。完了条件: 空 DB から `loaddata` で The Red Apple 1冊2ページが `/` と `/books/1/` で表示される。
- D-3: 一覧フィルタを DB クエリ化。完了条件: `?age=4` が DB 絞り込みで 200、クエリ1発＋空表示が統一される。
- D-4: モデル・view の最小テスト。完了条件: age 逆転 NG、unique NG、一覧・詳細 200、年齢絞り込みがテストで通る。
- D-5: セットアップ手順の混在 OS 対応。完了条件: Win WSL2／Mac／Linux の新規 PC で手順通り `200` になる。

## 9. 決定事項（v0.2 から継続）

- TTS は案Aで開始。`audio_url` は将来用に残す。
- 画像・音声はローカル `media/`（`MEDIA_ROOT=media/`, `MEDIA_URL=/media/`）。
- 対象年齢は必須、一覧で絞り込み。日本語訳あり。MVP では外部 API 連携なし。

## 10. 次アクション

1. この設計書をレビュー（過不足・優先順位）。
2. 合意分から Issue 化（D-1〜D-5 を1 Issue=1タスクで）。
3. `feature/design-*` で実装 → PR → main マージ。
