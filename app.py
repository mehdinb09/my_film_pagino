
import os
import sqlite3
import secrets
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import (
    Flask, request, redirect, url_for, session,
    flash, render_template_string, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE = Path(__file__).resolve().parent
DB_PATH = BASE / "cinema.db"
UPLOAD_DIR = BASE / "uploads"

UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me-now")

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
VIDEO_EXTENSIONS = {"mp4", "webm", "mov"}

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def initialize():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            image TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS films (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            poster TEXT DEFAULT '',
            video TEXT DEFAULT '',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            expires_at TEXT,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            days INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'pending',
            receipt TEXT DEFAULT '',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)

        if con.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            names = [
                "Family", "18+", "Stories", "Thick Cock",
                "Small Butt", "Big Breasts", "Small Breasts",
                "Big Butt", "Iranian", "Adult Cartoons"
            ]
            con.executemany(
                "INSERT INTO categories(name) VALUES(?)",
                [(name,) for name in names]
            )

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def allowed(filename, extensions):
    return (
        "." in filename and
        filename.rsplit(".", 1)[1].lower() in extensions
    )

def save_upload(field, extensions):
    file = request.files.get(field)
    if not file or not file.filename:
        return ""
    if not allowed(file.filename, extensions):
        raise ValueError("فرمت فایل مجاز نیست")
    name = secrets.token_hex(12) + "_" + secure_filename(file.filename)
    file.save(UPLOAD_DIR / name)
    return name

def page(content, title="BLACK CINEMA"):
    return render_template_string("""
    <!doctype html>
    <html lang="fa" dir="rtl">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{{ title }}</title>
      <style>
        *{box-sizing:border-box}
        body{margin:0;background:#09090d;color:#fff;font-family:tahoma,Arial}
        header{padding:22px;background:#15151d;border-bottom:1px solid #39202a}
        h1,h2{color:#ff294d}
        main{max-width:1100px;margin:25px auto;padding:16px}
        .card{background:linear-gradient(145deg,#1b1b25,#101015);
        border:1px solid #39202a;border-radius:18px;padding:20px;
        margin:14px 0;box-shadow:0 12px 35px #0008}
        input,textarea,select{width:100%;padding:13px;margin:8px 0;
        border-radius:10px;border:1px solid #444;background:#101016;color:white}
        button,.btn{display:inline-block;padding:12px 18px;
        border:0;border-radius:10px;background:#e92348;color:white;
        text-decoration:none;font-weight:bold;cursor:pointer}
        a{color:#ff536d}
        .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}
        .muted{color:#aaa;font-size:13px}
        img{max-width:100%;border-radius:12px}
        video{width:100%;border-radius:12px;background:#000}
      </style>
    </head>
    <body>
      <header><h2>BLACK CINEMA</h2><span class="muted">PREMIUM STREAMING PLATFORM</span></header>
      <main>{{ content|safe }}</main>
    </body>
    </html>
    """, content=content, title=title)

@app.route("/")
def home():
    with db() as con:
        categories = con.execute("SELECT * FROM categories").fetchall()
    html = "<h1>دنیای BLACK CINEMA</h1><div class='grid'>"
    for c in categories:
        html += f"""
        <a class='card' href='/category/{c['id']}'>
          <h2>{c['name']}</h2>
          <span class='muted'>مشاهده مجموعه</span>
        </a>"""
    html += "</div>"
    return page(html)

@app.route("/category/<int:category_id>")
def category(category_id):
    with db() as con:
        category = con.execute(
            "SELECT * FROM categories WHERE id=?",
            (category_id,)
        ).fetchone()
        films = con.execute(
            "SELECT * FROM films WHERE category_id=? ORDER BY id DESC",
            (category_id,)
        ).fetchall()
    if not category:
        abort(404)
    html = f"<h1>{category['name']}</h1><div class='grid'>"
    for film in films:
        html += f"""
        <div class='card'>
          <h3>{film['title']}</h3>
          <p>{film['description']}</p>
          <a class='btn' href='/watch/{film['id']}'>مشاهده</a>
        </div>"""
    html += "</div>"
    return page(html)

@app.route("/watch/<int:film_id>")
def watch(film_id):
    with db() as con:
        film = con.execute(
            "SELECT * FROM films WHERE id=?",
            (film_id,)
        ).fetchone()
    if not film:
        abort(404)
    if not session.get("admin"):
        abort(403)
    html = f"""
    <div class='card'>
      <h1>{film['title']}</h1>
      <p>{film['description']}</p>
      <video controls controlsList="nodownload">
        <source src="/media/{film['video']}">
      </video>
    </div>"""
    return page(html)

@app.route("/media/<path:filename>")
def media(filename):
    from flask import send_from_directory
    if not session.get("admin"):
        abort(403)
    return send_from_directory(UPLOAD_DIR, filename)

@app.route("/admin/login", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USER and check_password_hash(
            generate_password_hash(ADMIN_PASSWORD), password
        ):
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("نام کاربری یا رمز عبور اشتباه است")
    return page("""
    <div class='card'>
      <h1>ورود مدیر</h1>
      <form method='post'>
        <input name='username' placeholder='نام کاربری' required>
        <input name='password' type='password' placeholder='رمز عبور' required>
        <button>ورود به پنل مدیریت</button>
      </form>
    </div>
    """)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/admin")
@admin_required
def admin():
    with db() as con:
        films = con.execute("SELECT COUNT(*) FROM films").fetchone()[0]
        users = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        orders = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        categories = con.execute("SELECT * FROM categories").fetchall()
        pending = con.execute(
            "SELECT COUNT(*) FROM orders WHERE status='pending'"
        ).fetchone()[0]

    html = f"""
    <h1>CONTROL CENTER</h1>
    <p class='muted'>مرکز مدیریت BLACK CINEMA</p>
    <div class='grid'>
      <div class='card'><h2>{films}</h2>فیلم‌ها</div>
      <div class='card'><h2>{users}</h2>کاربران</div>
      <div class='card'><h2>{orders}</h2>سفارش‌ها</div>
      <div class='card'><h2>{pending}</h2>در انتظار بررسی</div>
    </div>
    <div class='card'>
      <h2>افزودن فیلم</h2>
      <form method='post' action='/admin/film' enctype='multipart/form-data'>
        <input name='title' placeholder='عنوان فیلم' required>
        <textarea name='description' placeholder='توضیحات'></textarea>
        <select name='category_id'>
          {''.join(f"<option value='{c['id']}'>{c['name']}</option>" for c in categories)}
        </select>
        <label>پوستر فیلم</label><input type='file' name='poster' accept='image/*'>
        <label>فایل ویدیو</label><input type='file' name='video' accept='video/*' required>
        <button>ثبت فیلم</button>
      </form>
    </div>
    <div class='card'>
      <h2>مدیریت دسته‌بندی‌ها</h2>
      <form method='post' action='/admin/category'>
        <input name='name' placeholder='نام دسته جدید' required>
        <button>افزودن دسته</button>
      </form>
    </div>
    <p><a class='btn' href='/admin/orders'>بررسی سفارش‌ها</a>
    <a class='btn' href='/logout'>خروج</a></p>
    """
    return page(html, "مدیریت BLACK CINEMA")

@app.route("/admin/film", methods=["POST"])
@admin_required
def add_film():
    try:
        poster = save_upload("poster", IMAGE_EXTENSIONS)
        video = save_upload("video", VIDEO_EXTENSIONS)
        with db() as con:
            con.execute("""
            INSERT INTO films(category_id,title,description,poster,video,created_at)
            VALUES(?,?,?,?,?,?)
            """, (
                request.form["category_id"],
                request.form["title"],
                request.form.get("description", ""),
                poster, video, datetime.utcnow().isoformat()
            ))
        flash("فیلم ثبت شد")
    except Exception as exc:
        flash(str(exc))
    return redirect(url_for("admin"))

@app.route("/admin/category", methods=["POST"])
@admin_required
def add_category():
    name = request.form.get("name", "").strip()
    if name:
        with db() as con:
            con.execute("INSERT INTO categories(name) VALUES(?)", (name,))
    return redirect(url_for("admin"))

@app.route("/admin/orders")
@admin_required
def orders():
    with db() as con:
        rows = con.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    html = "<h1>سفارش‌ها</h1>"
    for order in rows:
        html += f"""
        <div class='card'>
          سفارش #{order['id']} — {order['username']} — {order['amount']} تومان
          <p>وضعیت: {order['status']}</p>
          <a class='btn' href='/admin/order/{order['id']}/approve'>تأیید</a>
          <a class='btn' href='/admin/order/{order['id']}/reject'>رد</a>
        </div>"""
    return page(html)

@app.route("/admin/order/<int:order_id>/<action>")
@admin_required
def order_action(order_id, action):
    if action not in {"approve", "reject"}:
        abort(400)
    with db() as con:
        order = con.execute(
            "SELECT * FROM orders WHERE id=?",
            (order_id,)
        ).fetchone()
        if not order:
            abort(404)
        con.execute(
            "UPDATE orders SET status=? WHERE id=?",
            ("approved" if action == "approve" else "rejected", order_id)
        )
    return redirect(url_for("orders"))

@app.route("/health")
def health():
    return {"status": "ok", "app": "BLACK CINEMA"}

initialize()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
