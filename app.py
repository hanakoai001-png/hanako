import sys
from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

app = Flask(__name__)
DB_PATH = Path(__file__).parent / "todo.db"


# ─── DB初期化 ──────────────────────────────────────────
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                content    TEXT    NOT NULL,
                done       INTEGER NOT NULL DEFAULT 0,
                created_at TEXT    NOT NULL
            )
        """)
        conn.commit()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── 一覧表示 ──────────────────────────────────────────
@app.route("/")
def index():
    with get_db() as conn:
        todos = conn.execute(
            "SELECT * FROM todos ORDER BY done ASC, id DESC"
        ).fetchall()
    return render_template("index.html", todos=todos)


# ─── タスク追加 ────────────────────────────────────────
@app.route("/add", methods=["POST"])
def add():
    content = request.form.get("content", "").strip()
    if content:
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        with get_db() as conn:
            conn.execute(
                "INSERT INTO todos (content, created_at) VALUES (?, ?)",
                (content, now)
            )
            conn.commit()
    return redirect(url_for("index"))


# ─── 完了トグル ────────────────────────────────────────
@app.route("/toggle/<int:todo_id>")
def toggle(todo_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE todos SET done = CASE WHEN done = 0 THEN 1 ELSE 0 END WHERE id = ?",
            (todo_id,)
        )
        conn.commit()
    return redirect(url_for("index"))


# ─── タスク削除 ────────────────────────────────────────
@app.route("/delete/<int:todo_id>")
def delete(todo_id):
    with get_db() as conn:
        conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        conn.commit()
    return redirect(url_for("index"))


# ─── 起動 ──────────────────────────────────────────────
init_db()  # gunicorn起動時もDB初期化を実行

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    print(f"サーバー起動中: http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
