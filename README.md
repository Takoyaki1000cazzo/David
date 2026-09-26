# David（仕様案 v0.2）
英語で絵本を読み聞かせするアプリです。

> このREADMEは仕様案です。確定ではなく、チームで議論して更新する前提です。
> v0.2: 2026-09-07 に下記3点を確定（TTS / 保存先 / 年齢区分）。

## 1. 概要・目的
- 子ども向けに英語の絵本を「読む・聞く」できるWebアプリ
- 保護者・先生が絵本を登録し、子どもが選んで読み聞かせ再生できる
- MVPでは「選ぶ → 読む → 聞く」が最低限動くことを目標にする

## 2. 想定ユーザー
- 子ども（閲覧・再生メイン）
- 保護者 / 先生（絵本の登録・管理はDjango adminで実施）

## 3. MVP機能（案）
1. 絵本一覧：タイトル・表紙・対象年齢を表示（一覧で対象年齢による絞り込みあり）
2. 絵本詳細：ページごとの英文テキスト＋日本語訳＋画像を表示（※日本語訳ありで確定）
3. 読み聞かせ再生：Web Speech APIでページ単位に英文を音声再生（速度変更・リピート・連続読み上げ付き、日本語訳の表示ON/OFF付き）※案Aで確定
4. 管理画面：adminで絵本・ページ（日英含む）のCRUD
5. 会員登録・ログイン：保護者向けのアカウント管理（※当初対象外から実装に変更）
6. お気に入り：ログイン利用者が絵本を登録・一覧表示（`Favorite`）
7. 続きから読む：読書進捗（`ReadingProgress`）の記録・しおり・再開バナー
8. 管理者機能：公開／下書き状態管理、一括編集、複製（staff向け画面＋admin）

対象外（MVP後）：
- 録音・発音採点
- 外部API連携全般（※MVPでは不要で確定。ブラウザ標準の読み上げのみ使用）
- ネイティブ音声の自前生成基盤（最初はブラウザTTSで代替）

## 4. 画面イメージ（案）
- `/` トップ・一覧（年齢絞り込み・並び替え・つづきから読む導線付き）
- `/books/<id>/` 詳細（ページ送り＋再生ボタン＋速度・リピート・連続読み上げ・日本語表示切替・お気に入り・しおり）
- `/favorites/` お気に入り一覧（ログイン時）
- `/accounts/signup/`・`/accounts/login/` 会員登録・ログイン
- `/books/<id>/bulk-edit/` 一括編集（staff向け）
- `/admin/` 管理用

## 5. データモデル案
- `Book`: title, cover_image(`media/covers/`), age_min, age_max（※必須・対象年齢区分ありで確定）, description, description_ja（※日英両方持つ）, status（公開／下書き・既定は下書き）, published_at, created_at
- `Page`: book(FK), page_no, text_en, text_ja（※確定）, image(`media/pages/`), audio_url(nullable), created_at
- `Favorite`: user(FK), book(FK) — お気に入り登録
- `ReadingProgress`: user(FK), book(FK), last_page_no — 続きから読む・しおり用

保存先方針（確定）：
- 画像・音声はローカル `media/` 配下に保存（MVP確定）
- `MEDIA_ROOT=media/`, `MEDIA_URL=/media/` を想定

音声方針（確定）：
- MVPは案A: ブラウザのWeb Speech APIで無料・即実装（確定）
- 案B: バックエンドでTTS生成してMP3保存（高品質だが工数大）→ 将来対応
- 将来Bに移行できるよう `audio_url` を残す

## 6. 技術スタック
- Backend: Django==5.2.17
- DB: MySQL 8.4（docker: `david-mysql`）
- Lib: mysqlclient==2.2.8, python-dotenv==1.2.3, Pillow==11.3.0
- Infra(dev): Docker Compose

## 7. 開発手順（概要）
```bash
git checkout main && git pull origin main
cp .env.example .env  # DJANGO_SECRET_KEYのみ生成して置換
docker compose up -d
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py loaddata sample_books  # サンプル絵本データ投入（The Red Apple）
python manage.py runserver
```
詳細はチームチャット送付の手順書を参照。`.env` の実値は共有しない。

## 8. ロードマップ案
- [x] 初期セットアップ（#1 マージ済み）
- [x] `books` アプリ＋モデル＋admin登録
- [x] 一覧・詳細画面（テンプレートのみ）
- [x] Web Speech APIによる読み上げ
- [x] 画像アップロード・表紙表示
- [x] 会員登録・ログイン
- [x] お気に入り登録・一覧
- [x] 続きから読む（読書進捗・しおり）
- [x] 連続読み聞かせ
- [x] 管理者機能（公開／下書き・一括編集・複製）
- [x] 一覧の並び替え・管理者向け画面UI
- [x] フリー絵本seed・画像とクレジット表記
- [x] CI品質チェック（マイグレーション・静的ファイル検証）

## 9. 決定事項 / 要議論
- [x] TTSは案Aで始めてよいか？ → 案A（Web Speech API）で確定
- [x] 画像・音声の保存先（ローカル `media/` でよいか？） → ローカル `media/` で確定
- [x] 対象年齢の区分は必要か？ → 必要で確定（`age_min` / `age_max` 必須、一覧で絞り込み表示）
- [x] 日本語訳を表示するか？ → ありで確定
- [x] 会員登録・ログインを入れるか？ → ありに変更（保護者向け・当初対象外から実装）
- [x] 絵本の公開／下書き管理は必要か？ → 必要で確定（`status` による表示制御）
