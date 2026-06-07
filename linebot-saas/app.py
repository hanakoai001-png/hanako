import os
from flask import Flask, request, abort, render_template, redirect
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
from bot_logic import handle_message
from stripe_handler import create_checkout_session, handle_webhook, process_event

load_dotenv()

app = Flask(__name__)

configuration = Configuration(
    access_token=os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
)
handler = WebhookHandler(os.environ.get("LINE_CHANNEL_SECRET"))


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def on_message(event: MessageEvent):
    user_text = event.message.text
    reply_text = handle_message(user_text)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)],
            )
        )


# ===== Stripe ルート =====

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/create-checkout-session", methods=["POST"])
def create_checkout():
    base_url = request.host_url.rstrip("/")
    try:
        checkout_url = create_checkout_session(base_url)
        return redirect(checkout_url, code=303)
    except Exception as e:
        app.logger.error(f"Stripe Checkout error: {e}")
        abort(500)


@app.route("/success")
def success():
    return render_template("success.html")


@app.route("/cancel")
def cancel():
    return render_template("cancel.html")


@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = handle_webhook(payload, sig_header)
    except ValueError as e:
        app.logger.warning(f"Webhook error: {e}")
        abort(400)

    result = process_event(event)
    app.logger.info(f"Webhook processed: {result}")
    return {"status": "ok"}, 200


# ===== エントリポイント =====

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
