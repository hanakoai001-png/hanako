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
SYSTEM_PROMPT = (
    "あなたは親切で丁寧なAIアシスタントです。"
    "LINEのメッセージに対して、日本語で簡潔にわかりやすく返信してください。"
    "返信は300文字以内に収めるよう心がけてください。"
)


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
