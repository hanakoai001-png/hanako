import sys
import os
import hashlib
import hmac
import base64
from pathlib import Path

from flask import Flask, request, abort
from dotenv import load_dotenv
import anthropic
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# ─── 環境変数読み込み ──────────────────────────────────
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

sys.stdout.reconfigure(encoding="utf-8")

app = Flask(__name__)

# ─── LINE 設定 ─────────────────────────────────────────
LINE_CHANNEL_SECRET       = os.environ.get("LINE_CHANNEL_SECRET", "").strip()
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()

handler       = WebhookHandler(LINE_CHANNEL_SECRET)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)

# ─── Anthropic 設定 ────────────────────────────────────
anthropic_client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip()
)

CLAUDE_MODEL  = "claude-sonnet-4-5"
SYSTEM_PROMPT = """
あなたは「花屋はなとく 泉北店」の公式LINEアシスタントです。
お客様からのお問い合わせに、丁寧で親しみやすい言葉遣いで対応してください。

【店舗情報】
- 店名：花屋はなとく 泉北店
- 住所：大阪府堺市中区小坂270 アンディ泉北
- 営業時間：10:00〜19:00
- 定休日：不明な場合は「お電話にてご確認ください」と案内する

【得意なもの・取り扱い】
- お祝い花（誕生日・開店祝い・記念日など）
- 御供花（葬儀・法事・お盆など）
- カジュアルフラワー（日常使い・プレゼントなど）
- その他、ご要望に応じてアレンジメント・花束の作成が可能

【対応スタイル】
- 丁寧で親しみやすいトーンで返信する
- 語尾は「です・ます調」を使う
- お客様の気持ちに寄り添い、温かみのある表現を心がける
- 返信は300文字以内に収める
- 価格など不明な情報は「詳しくは店舗までお気軽にお問い合わせください😊」と案内する
- 絵文字を適度に使って親しみやすさを演出する（🌸🌷💐など）

【よくある質問への対応例】
- 営業時間を聞かれたら：10:00〜19:00とお伝えする
- 場所を聞かれたら：大阪府堺市中区小坂270 アンディ泉北とお伝えする
- お祝い花の相談：ご予算・用途・ご希望をお聞きして、喜んで対応する旨を伝える
- 御供花の相談：丁寧に心を込めて対応する旨を伝える
""".strip()


# ─── Claude に問い合わせ ───────────────────────────────
def ask_claude(user_message: str) -> str:
    try:
        response = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except anthropic.APIError as e:
        print(f"[Claude APIエラー] {e}")
        return "申し訳ありません。現在AIに接続できません。しばらくしてからもう一度お試しください。"
    except Exception as e:
        print(f"[予期しないエラー] {e}")
        return "エラーが発生しました。もう一度メッセージを送ってみてください。"


# ─── LINE Webhook エンドポイント ───────────────────────
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body      = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("[LINE] 署名検証失敗")
        abort(400)

    return "OK", 200


# ─── テキストメッセージのハンドラ ──────────────────────
@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event: MessageEvent):
    user_message = event.message.text
    reply_token  = event.reply_token

    print(f"[受信] {user_message}")

    # Claude に返信を生成させる
    reply_text = ask_claude(user_message)

    print(f"[返信] {reply_text}")

    # LINE に返信を送信
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=reply_text)],
            )
        )


# ─── 接続確認エンドポイント ────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return {
        "status": "ok",
        "line_secret_set":    bool(LINE_CHANNEL_SECRET),
        "line_token_set":     bool(LINE_CHANNEL_ACCESS_TOKEN),
        "anthropic_key_set":  bool(os.environ.get("ANTHROPIC_API_KEY")),
        "model":              CLAUDE_MODEL,
    }, 200


# ─── 起動 ──────────────────────────────────────────────
if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5002))
    debug = os.environ.get("FLASK_ENV") != "production"
    print(f"LINE Bot サーバー起動中: http://127.0.0.1:{port}")
    print(f"Webhook URL: http://127.0.0.1:{port}/callback")
    app.run(host="0.0.0.0", port=port, debug=debug)
