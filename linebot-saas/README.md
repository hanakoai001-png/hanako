# LINE Bot SaaS

FAQ自動返信・営業時間外対応・Claude APIによる自然返答を備えたLINEボット。

## 機能

| トリガーワード | 返答 |
|---|---|
| 営業時間 | 営業時間は10時〜19時です |
| 料金 / 価格 / 費用 | 料金プランのご案内 |
| 予約 | 予約受付案内 |
| アクセス / 住所 | 所在地・最寄り駅案内 |
| 19時〜翌10時 | 営業時間外メッセージ |
| その他 | Claude APIで自動返答 |

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

```bash
cp .env.example .env
# .env を編集して各トークンを設定する
```

### 3. ローカル起動

```bash
python app.py
```

### 4. Webhook URLの設定

ngrok などでローカルを公開し、LINE Developers コンソールの Webhook URL に設定：

```
https://<your-domain>/callback
```

## Render へのデプロイ

1. Render ダッシュボードで **New Web Service** を作成
2. リポジトリを接続
3. 以下を設定：

| 項目 | 値 |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app` |
| Environment Variables | `.env.example` の3変数を入力 |

4. デプロイ後、発行されたURLの `/callback` を LINE Developers の Webhook URL に設定

## ファイル構成

```
linebot-saas/
├── app.py          # Flask アプリ・Webhook エンドポイント
├── bot_logic.py    # FAQ判定・営業時間チェック・Claude API呼び出し
├── requirements.txt
├── .env.example    # 環境変数テンプレート
└── README.md
```
