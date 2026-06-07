import os
import stripe

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

PRICE_ID = os.environ.get("STRIPE_PRICE_ID")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")


def create_checkout_session(base_url: str) -> str:
    """Stripe Checkout Session を作成して URL を返す"""
    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        line_items=[
            {
                "price": PRICE_ID,
                "quantity": 1,
            }
        ],
        success_url=f"{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/cancel",
    )
    return session.url


def handle_webhook(payload: bytes, sig_header: str) -> dict:
    """
    Stripe Webhook を検証してイベントを返す。
    署名検証失敗時は ValueError を raise する。
    """
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, WEBHOOK_SECRET
        )
    except stripe.error.SignatureVerificationError as e:
        raise ValueError(f"Webhook signature verification failed: {e}") from e

    return event


def process_event(event: dict) -> str:
    """
    イベント種別に応じた処理を行い、処理内容を文字列で返す。
    必要に応じてケースを追加してください。
    """
    event_type = event.get("type", "")

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_details", {}).get("email", "不明")
        subscription_id = session.get("subscription", "不明")
        print(f"[Stripe] 支払い完了: email={customer_email}, subscription={subscription_id}")
        # TODO: DB保存・LINEへの通知などをここに追加
        return f"subscription activated: {subscription_id}"

    if event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        print(f"[Stripe] サブスクリプション解約: id={subscription.get('id')}")
        # TODO: 解約処理をここに追加
        return f"subscription cancelled: {subscription.get('id')}"

    # その他のイベントは無視
    return f"unhandled event: {event_type}"
