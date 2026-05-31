import sys
import os
import sqlite3
import hashlib
import secrets
from datetime import datetime
from pathlib import Path
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from dotenv import load_dotenv
import stripe

# ─── 環境変数読み込み（明示パス指定） ────────────────────
ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

sys.stdout.reconfigure(encoding="utf-8")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# Stripe設定
stripe.api_key     = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_PUBLIC_KEY  = os.environ.get("STRIPE_PUBLIC_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
MONTHLY_PRICE = 980  # 円

DB_PATH = Path(__file__).parent / "users.db"


# ─── パスワードハッシュ ────────────────────────────────
def hash_password(password: str, salt: str = None):
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 260000
    ).hex()
    return hashed, salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    return hash_password(password, salt)[0] == hashed


# ─── DB初期化 ──────────────────────────────────────────
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                username            TEXT    NOT NULL UNIQUE,
                email               TEXT    NOT NULL UNIQUE,
                password            TEXT    NOT NULL,
                salt                TEXT    NOT NULL,
                plan                TEXT    NOT NULL DEFAULT 'free',
                stripe_customer_id  TEXT,
                stripe_subscription_id TEXT,
                plan_started_at     TEXT,
                created_at          TEXT    NOT NULL
            )
        """)
        # 既存テーブルへのカラム追加（マイグレーション）
        existing = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        migrations = {
            "plan":                    "TEXT NOT NULL DEFAULT 'free'",
            "stripe_customer_id":      "TEXT",
            "stripe_subscription_id":  "TEXT",
            "plan_started_at":         "TEXT",
        }
        for col, definition in migrations.items():
            if col not in existing:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
        conn.commit()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── デコレータ ───────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("ログインが必要です。", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def paid_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        with get_db() as conn:
            user = conn.execute(
                "SELECT plan FROM users WHERE id = ?", (session["user_id"],)
            ).fetchone()
        if not user or user["plan"] != "paid":
            flash("この機能は有料プランのみご利用いただけます。", "warning")
            return redirect(url_for("pricing"))
        return f(*args, **kwargs)
    return decorated


# ─── ルート ───────────────────────────────────────────
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# ── 会員登録 ──
@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")

        if not username or not email or not password:
            flash("すべての項目を入力してください。", "error")
            return render_template("register.html")
        if len(username) < 2:
            flash("ユーザー名は2文字以上で入力してください。", "error")
            return render_template("register.html")
        if len(password) < 6:
            flash("パスワードは6文字以上で設定してください。", "error")
            return render_template("register.html")
        if password != confirm:
            flash("パスワードが一致しません。", "error")
            return render_template("register.html")

        hashed, salt = hash_password(password)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO users (username, email, password, salt, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (username, email, hashed, salt, now)
                )
                conn.commit()
            flash("登録が完了しました！ログインしてください。", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("そのユーザー名またはメールアドレスはすでに使用されています。", "error")
            return render_template("register.html")

    return render_template("register.html")


# ── ログイン ──
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("メールアドレスとパスワードを入力してください。", "error")
            return render_template("login.html")

        with get_db() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE email = ?", (email,)
            ).fetchone()

        if user and verify_password(password, user["password"], user["salt"]):
            session["user_id"]  = user["id"]
            session["username"] = user["username"]
            flash(f"おかえりなさい、{user['username']}さん！", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("メールアドレスまたはパスワードが正しくありません。", "error")
            return render_template("login.html")

    return render_template("login.html")


# ── ダッシュボード ──
@app.route("/dashboard")
@login_required
def dashboard():
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()
    return render_template("dashboard.html", user=user)


# ── ログアウト ──
@app.route("/logout")
def logout():
    username = session.get("username", "")
    session.clear()
    flash(f"{username}さん、またね！", "info")
    return redirect(url_for("login"))


# ─── 料金プラン画面 ────────────────────────────────────
@app.route("/pricing")
@login_required
def pricing():
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()
    return render_template(
        "pricing.html",
        user=user,
        stripe_public_key=STRIPE_PUBLIC_KEY,
        monthly_price=MONTHLY_PRICE
    )


# ─── Stripe接続チェック（診断用） ────────────────────
@app.route("/stripe-status")
@login_required
def stripe_status():
    # 毎回 .env を再読込して最新キーを取得
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    current_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    stripe.api_key = current_key  # グローバルキーも更新

    result = {
        "key_set":    bool(current_key),
        "key_prefix": current_key[:12] + "..." if current_key else "未設定",
        "key_length": len(current_key),
        "key_suffix": current_key[-6:] if current_key else "",
    }
    try:
        stripe.Balance.retrieve()
        result["connected"] = True
        result["message"]   = "Stripe API 接続成功"
    except stripe.AuthenticationError as e:
        result["connected"] = False
        result["message"]   = f"認証失敗: {e.user_message}"
        result["hint"]      = "Stripeダッシュボード → Developers → API keys でキーを確認してください"
    except Exception as e:
        result["connected"] = False
        result["message"]   = str(e)
    return jsonify(result)


# ─── Stripe決済セッション作成 ─────────────────────────
@app.route("/create-checkout-session", methods=["POST"])
@login_required
def create_checkout_session():
    # 毎回 .env を再読込
    load_dotenv(dotenv_path=ENV_PATH, override=True)
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()

    if not stripe.api_key:
        flash("Stripe APIキーが設定されていません。.envファイルを確認してください。", "error")
        return redirect(url_for("pricing"))

    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()

    try:
        # Stripe顧客を作成または取得
        customer_id = user["stripe_customer_id"]
        if not customer_id:
            customer = stripe.Customer.create(
                email=user["email"],
                name=user["username"],
                metadata={"user_id": str(user["id"])},
            )
            customer_id = customer.id
            with get_db() as conn:
                conn.execute(
                    "UPDATE users SET stripe_customer_id = ? WHERE id = ?",
                    (customer_id, user["id"])
                )
                conn.commit()

        # Checkoutセッション作成
        base_url = request.host_url.rstrip("/")
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "jpy",
                    "unit_amount": MONTHLY_PRICE,
                    "recurring": {"interval": "month"},
                    "product_data": {
                        "name": "プレミアムプラン",
                        "description": "月額980円・全機能使い放題",
                    },
                },
                "quantity": 1,
            }],
            mode="subscription",
            metadata={"user_id": str(session["user_id"])},
            success_url=f"{base_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}/pricing",
        )
        return redirect(checkout_session.url, code=303)

    except stripe.AuthenticationError:
        flash(
            "Stripe APIキーが無効です。"
            " Stripeダッシュボード（stripe.com）→ Developers → API keys"
            " でシークレットキーを確認し、.envを更新してください。",
            "error"
        )
        return redirect(url_for("pricing"))
    except stripe.StripeError as e:
        flash(f"決済エラー: {e.user_message}", "error")
        return redirect(url_for("pricing"))


# ─── 決済成功コールバック ──────────────────────────────
@app.route("/payment/success")
@login_required
def payment_success():
    session_id = request.args.get("session_id")
    if not session_id:
        return redirect(url_for("dashboard"))

    try:
        checkout_session = stripe.checkout.Session.retrieve(
            session_id,
            expand=["subscription"]
        )
        # 支払いステータス確認（Stripeオブジェクトは属性アクセス）
        payment_status  = checkout_session.payment_status
        sub             = checkout_session.subscription
        subscription_id = sub.id if hasattr(sub, "id") else sub

        if payment_status in ("paid", "no_payment_required") or subscription_id:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with get_db() as conn:
                conn.execute(
                    "UPDATE users SET plan = 'paid', stripe_subscription_id = ?,"
                    " plan_started_at = ? WHERE id = ?",
                    (subscription_id, now, session["user_id"])
                )
                conn.commit()
            flash("🎉 有料プランへのアップグレードが完了しました！", "success")
        else:
            flash("決済が完了していません。もう一度お試しください。", "warning")

    except stripe.StripeError as e:
        flash(f"確認エラー: {e.user_message}", "error")

    return redirect(url_for("dashboard"))


# ─── Stripe Webhook（本番用・自動プラン更新） ──────────
@app.route("/webhook/stripe", methods=["POST"])
def stripe_webhook():
    payload   = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            event = stripe.Event.construct_from(
                __import__("json").loads(payload), stripe.api_key
            )
    except (ValueError, stripe.SignatureVerificationError):
        return "Bad Request", 400

    # サブスクリプション有効化
    if event["type"] in ("customer.subscription.created", "invoice.payment_succeeded"):
        data = event["data"]["object"]
        customer_id = data.customer
        sub_id = data.id if event["type"].startswith("customer") else data.subscription
        if customer_id:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with get_db() as conn:
                conn.execute(
                    "UPDATE users SET plan = 'paid', stripe_subscription_id = ?,"
                    " plan_started_at = ? WHERE stripe_customer_id = ?",
                    (sub_id, now, customer_id)
                )
                conn.commit()

    # サブスクリプション解約・失効
    elif event["type"] in ("customer.subscription.deleted", "invoice.payment_failed"):
        data = event["data"]["object"]
        customer_id = data.customer
        if customer_id:
            with get_db() as conn:
                conn.execute(
                    "UPDATE users SET plan = 'free', stripe_subscription_id = NULL,"
                    " plan_started_at = NULL WHERE stripe_customer_id = ?",
                    (customer_id,)
                )
                conn.commit()

    return "OK", 200


# ─── サブスクリプション解約 ───────────────────────────
@app.route("/cancel-subscription", methods=["POST"])
@login_required
def cancel_subscription():
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()

    if not user["stripe_subscription_id"]:
        flash("有効なサブスクリプションが見つかりません。", "error")
        return redirect(url_for("dashboard"))

    try:
        stripe.Subscription.cancel(user["stripe_subscription_id"])
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET plan = 'free', stripe_subscription_id = NULL,"
                " plan_started_at = NULL WHERE id = ?",
                (session["user_id"],)
            )
            conn.commit()
        flash("サブスクリプションを解約しました。", "info")

    except stripe.AuthenticationError:
        flash("Stripe APIキーが無効です。.envファイルを確認してください。", "error")
    except stripe.StripeError as e:
        flash(f"解約エラー: {e.user_message}", "error")

    return redirect(url_for("dashboard"))


# ─── 起動 ──────────────────────────────────────────────
init_db()

if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_ENV") != "production"
    print(f"サーバー起動中: http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
