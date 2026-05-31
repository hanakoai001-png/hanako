import sys
import os
import sqlite3
import hashlib
import secrets
from pathlib import Path
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)

sys.stdout.reconfigure(encoding="utf-8")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

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
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    NOT NULL UNIQUE,
                email      TEXT    NOT NULL UNIQUE,
                password   TEXT    NOT NULL,
                salt       TEXT    NOT NULL,
                created_at TEXT    NOT NULL
            )
        """)
        conn.commit()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── ログイン必須デコレータ ────────────────────────────
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("ログインが必要です。", "warning")
            return redirect(url_for("login"))
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

        # バリデーション
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
        from datetime import datetime
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
            session["user_id"]   = user["id"]
            session["username"]  = user["username"]
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


# ─── 起動 ──────────────────────────────────────────────
init_db()

if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_ENV") != "production"
    print(f"サーバー起動中: http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
