
import os
import sqlite3
import secrets
import requests
from pathlib import Path
from functools import wraps
from flask import Flask, request, redirect, session, flash, render_template_string, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"
PRIVATE = BASE / "private_uploads"
UPLOADS.mkdir(exist_ok=True)
PRIVATE.mkdir(exist_ok=True)
DB = BASE / "cinema.db"

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me-now")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")

ALLOWED = {"jpg", "jpeg", "png", "webp"}

CATEGORIES = [
    "Family", "18+", "Stories", "Thick Cock",
    "Small Butt", "Big Breasts", "Small Breasts",
    "Big Butt", "Iranian", "Adult Cartoons"
]

STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
*{box-sizing:border-box}
:root{--red:#ed2448;--glass:rgba(12,12,18,.52)}
body{
 margin:0;color:#fff;font-family:Inter,Arial,sans-serif;
 background:#08080d;
 background-image:linear-gradient(rgba(5,5,10,.55),rgba(5,5,10,.82)),
 var(--wallpaper,radial-gradient(circle at top,#401321,#08080d 65%));
 background-size:cover;background-position:center;background-attachment:fixed;
 min-height:100vh
}
a{color:inherit;text-decoration:none}
nav{
 position:sticky;top:0;z-index:5;padding:17px 5%;
 display:flex;justify-content:space-between;align-items:center;
 background:rgba(5,5,10,.65);backdrop-filter:blur(18px);
 border-bottom:1px solid #ffffff20
}
.brand{font-size:21px;font-weight:900;letter-spacing:2px}
.brand span{color:var(--red)}
nav div{display:flex;gap:18px;font-size:13px}
nav a:hover{color:#ff7189}
main{width:min(1150px,92%);margin:35px auto 70px;min-height:75vh}
.hero{
 padding:48px 25px;border:1px solid #ffffff35;border-radius:25px;
 background:linear-gradient(120deg,rgba(20,15,24,.65),rgba(30,10,20,.25));
 backdrop-filter:blur(14px);text-align:center
}
.hero h1{font-size:clamp(35px,7vw,65px);margin:10px}
.hero h1 span{color:var(--red)}
.hero p{color:#ccc;line-height:2}
h2{font-size:22px;margin-top:38px}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin-top:20px}
.card{
 position:relative;display:block;min-height:210px;overflow:hidden;
 border:1px solid #ffffff40;border-radius:19px;
 background:var(--glass);backdrop-filter:blur(13px);
 box-shadow:0 12px 35px #0007;transition:.25s
}
.card:hover{transform:translateY(-5px);border-color:#ed2448}
.card img{width:100%;height:205px;object-fit:cover;display:block}
.card .shade{
 position:absolute;inset:0;
 background:linear-gradient(transparent 15%,rgba(0,0,0,.85));
}
.card .cardtext{
 position:absolute;bottom:0;left:0;right:0;padding:17px;
 background:rgba(15,12,18,.25);backdrop-filter:blur(5px)
}
.card h3{margin:0;font-size:19px}
.card p{font-size:12px;color:#ddd;margin:8px 0 0}
.placeholder{
 height:205px;display:grid;place-items:center;
 font-size:35px;color:#ed3150;
 background:linear-gradient(135deg,#27111c,#101018)
}
.btn{
 display:inline-block;padding:13px 21px;border:0;border-radius:10px;
 background:var(--red);color:white;font-weight:800;cursor:pointer;
 font:inherit
}
.btn:hover{background:#b81435}
.panel{
 padding:22px;border:1px solid #ffffff30;border-radius:17px;
 background:rgba(12,12,18,.76);backdrop-filter:blur(14px);
 margin:15px 0
}
input,textarea,select{
 display:block;width:100%;padding:12px;margin:8px 0 17px;
 background:#101018;color:white;border:1px solid #ffffff40;
 border-radius:8px;font:inherit
}
input[type=checkbox]{display:inline;width:auto;margin:0 8px}
input[type=file]{font-size:12px}
label{display:block;color:#eee;margin-top:10px}
.option{
 display:flex;justify-content:space-between;align-items:center;
 gap:10px;padding:14px 5px;border-bottom:1px solid #ffffff20
}
.option b{color:#ff7890;white-space:nowrap}
small{color:#aaa}
.notice{padding:13px;background:#451522;border-radius:9px;margin:12px 0}
footer{text-align:center;padding:25px;color:#aaa;border-top:1px solid #ffffff20}
.film img{width:100%;height:190px;object-fit:cover;border-radius:12px}
.total{font-size:22px;color:#ff7189;font-weight:900;padding:15px 0}
.order{padding:18px 0;border-bottom:1px solid #ffffff25}
.order img{max-width:180px;border-radius:10px;display:block;margin:12px 0}
@media(max-width:700px){
 .grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
 .card img,.placeholder{height:155px}
 .card{min-height:155px}
 nav{padding:14px 4%}
 nav div{gap:10px;font-size:11px}
 main{width:94%;margin-top:20px}
}
@media(max-width:390px){
 .grid{grid-template-columns:1fr}
 .card img,.placeholder{height:200px}
}
"""

def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def setup():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, description TEXT, image TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS options(
        id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,price INTEGER)""")
        c.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,customer TEXT,telegram TEXT,
        details TEXT,total INTEGER,image TEXT,
        status TEXT DEFAULT 'در انتظار پرداخت')""")
        c.execute("""CREATE TABLE IF NOT EXISTS films(
        id INTEGER PRIMARY KEY AUTOINCREMENT,category_id INTEGER,
        title TEXT,description TEXT,poster TEXT,video_url TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS settings(
        name TEXT PRIMARY KEY,value TEXT)""")
        count = c.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if count == 0:
            for name in CATEGORIES:
                c.execute(
                    "INSERT INTO categories(title,description,image) VALUES(?,?,?)",
                    (name, "Explore collection", "")
                )

setup()

def setting(name):
    with connect() as c:
        row = c.execute("SELECT value FROM settings WHERE name=?", (name,)).fetchone()
    return row["value"] if row else ""

def save_setting(name, value):
    with connect() as c:
        c.execute(
            "INSERT OR REPLACE INTO settings(name,value) VALUES(?,?)",
            (name, value)
        )

def page(content, **data):
    bg = setting("background")
    body = render_template_string(content, **data)
    return render_template_string("""
    <!doctype html><html lang="en"><head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="description" content="BLACK CINEMA">
    <title>BLACK CINEMA</title>
    <style>
    """ + STYLE + """
    </style></head>
    <body style="--wallpaper:url('/media/{{bg}}')">
    <nav>
      <a class="brand" href="/">BLACK <span>CINEMA</span></a>
      <div><a href="/">Home</a><a href="/custom">Create</a>
      <a href="/login">Admin</a></div>
    </nav>
    <main>
    {% with msgs=get_flashed_messages() %}
    {% for m in msgs %}<div class="notice">{{m}}</div>{% endfor %}
    {% endwith %}
    """ + body + """
    </main><footer>BLACK CINEMA</footer></body></html>
    """, bg=bg)

def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("admin"):
            return redirect("/login")
        return fn(*a, **kw)
    return wrapper

def upload_image(file, private=False):
    if not file or not file.filename:
        return ""
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED:
        return None
    name = secrets.token_hex(16) + "." + ext
    folder = PRIVATE if private else UPLOADS
    file.save(folder / name)
    return name

def telegram_notice(order_id, customer, username, total, details):
    if not BOT_TOKEN or not ADMIN_CHAT_ID:
        return
    message = (
        f"BLACK CINEMA ORDER #{order_id}\n"
        f"Customer: {customer}\nTelegram: {username}\n"
        f"Price: {total:,} Toman\nDetails: {details}"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": ADMIN_CHAT_ID, "text": message},
            timeout=8
        )
    except Exception:
        pass

@app.route("/")
def home():
    if not session.get("adult"):
        return redirect("/age-check")
    with connect() as c:
        cats = c.execute("SELECT * FROM categories ORDER BY id").fetchall()
    return page("""
    <section class="hero">
      <small>BLACK CINEMA</small>
      <h1>Choose Your <span>World</span></h1>
      <p>Explore the collections</p>
    </section>
    <h2>Categories</h2>
    <div class="grid">
    {% for x in cats %}
      <a class="card" href="/category/{{x.id}}">
      {% if x.image %}
        <img src="/media/{{x.image}}" alt="">
      {% else %}
        <div class="placeholder">BC</div>
      {% endif %}
      <div class="shade"></div>
      <div class="cardtext"><h3>{{x.title}}</h3>
      <p>Explore collection →</p></div></a>
    {% endfor %}
      <a class="card" href="/custom">
        <div class="placeholder">＋</div><div class="shade"></div>
        <div class="cardtext"><h3>Create Your Own Private Movie</h3>
        <p>Choose options and see the price →</p></div>
      </a>
    </div>
    """, cats=cats)

@app.route("/age-check", methods=["GET", "POST"])
def age_check():
    if request.method == "POST":
        if request.form.get("confirm") == "yes":
            session["adult"] = True
            return redirect("/")
        return "Access denied", 403
    return page("""
    <section class="hero">
    <h1>18+ <span>Only</span></h1>
    <p>This website is intended only for adults aged 18 or older.
    All content must be lawful and involve consenting adults.</p>
    <form method="post">
    <button class="btn" name="confirm" value="yes">I am 18 or older</button>
    </form>
    </section>
    """)

@app.route("/category/<int:cid>")
def category(cid):
    if not session.get("adult"):
        return redirect("/age-check")
    with connect() as c:
        cat = c.execute("SELECT * FROM categories WHERE id=?", (cid,)).fetchone()
        films = c.execute("SELECT * FROM films WHERE category_id=? ORDER BY id DESC", (cid,)).fetchall()
    if not cat:
        return "Category not found", 404
    return page("""
    <h1>{{cat.title}}</h1>
    <p>{{cat.description}}</p>
    <div class="grid">
    {% for f in films %}
      <article class="card film">
      {% if f.poster %}<img src="/media/{{f.poster}}" alt="">
      {% else %}<div class="placeholder">BC</div>{% endif %}
      <div class="cardtext"><h3>{{f.title}}</h3>
      <p>{{f.description}}</p>
      {% if f.video_url %}<a class="btn" href="{{f.video_url}}" target="_blank" rel="noopener">Open</a>{% endif %}
      </div></article>
    {% else %}
      <p>No films have been added to this collection yet.</p>
    {% endfor %}
    </div><p><a href="/">← Home</a></p>
    """, cat=cat, films=films)

@app.route("/custom", methods=["GET", "POST"])
def custom():
    if not session.get("adult"):
        return redirect("/age-check")
    with connect() as c:
        opts = c.execute("SELECT * FROM options ORDER BY id").fetchall()
    if request.method == "POST":
        customer = request.form.get("customer", "").strip()
        telegram = request.form.get("telegram", "").strip().lstrip("@")
        image = request.files.get("reference")
        if not customer or not telegram or not image or not image.filename:
            flash("Enter your name, Telegram ID and reference image.")
            return redirect("/custom")
        filename = upload_image(image, private=True)
        if filename is None:
            flash("Use JPG, PNG or WEBP image.")
            return redirect("/custom")
        chosen, total = [], 0
        with connect() as c:
            for raw in request.form.getlist("options"):
                if raw.isdigit():
                    opt = c.execute(
                        "SELECT * FROM options WHERE id=?", (int(raw),)
                    ).fetchone()
                    if opt:
                        chosen.append(f"{opt['title']} ({opt['price']:,} Toman)")
                        total += opt["price"]
            details = ", ".join(chosen) or "No extra options"
            cur = c.execute("""INSERT INTO orders
            (customer,telegram,details,total,image) VALUES(?,?,?,?,?)""",
            (customer, "@" + telegram, details, total, filename))
            oid = cur.lastrowid
        telegram_notice(oid, customer, "@" + telegram, total, details)
        return page("""
        <section class="hero"><h1>Order Received</h1>
        <h2>Order #{{oid}}</h2><div class="total">{{'{:,}'.format(total)}} Toman</div>
        <p>Your request is pending. No online payment has been processed.</p>
        <a class="btn" href="/">Home</a></section>
        """, oid=oid, total=total)
    return page("""
    <h1>Create Your Own Private Movie</h1>
    <form class="panel" method="post" enctype="multipart/form-data">
    <label>Name<input name="customer" required></label>
    <label>Telegram ID<input name="telegram" placeholder="@username" required></label>
    <h3>Choose options</h3>
    {% for o in opts %}
      <label class="option">
      <span><input type="checkbox" name="options" value="{{o.id}}" data-price="{{o.price}}">
      {{o.title}}</span><b>{{"{:,}".format(o.price)}} Toman</b></label>
    {% endfor %}
    <div class="total">Total: <span id="total">0</span> Toman</div>
    <label>Reference image<input type="file" name="reference" accept="image/*" required></label>
    <button class="btn">Submit order</button>
    </form>
    <script>
    const boxes=document.querySelectorAll('input[name="options"]');
    function calc(){
      let sum=0;
      boxes.forEach(x=>{if(x.checked)sum+=Number(x.dataset.price)});
      document.getElementById('total').textContent=sum.toLocaleString();
    }
    boxes.forEach(x=>x.addEventListener('change',calc));
    </script>
    <small>Order submission does not mean payment. Online payment is not connected yet.</small>
    """, opts=opts)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USER and secrets.compare_digest(
            request.form.get("password", ""), ADMIN_PASSWORD
        ):
            session["admin"] = True
            return redirect("/admin")
        flash("Incorrect username or password.")
    return page("""
    <h1>Admin Login</h1>
    <form class="panel" method="post">
    <label>Username<input name="username" required></label>
    <label>Password<input name="password" type="password" required></label>
    <button class="btn">Login</button></form>
    """)

@app.route("/admin")
@admin_required
def admin():
    with connect() as c:
        cats = c.execute("SELECT * FROM categories ORDER BY id").fetchall()
        opts = c.execute("SELECT * FROM options ORDER BY id DESC").fetchall()
        orders = c.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
        films = c.execute("SELECT * FROM films ORDER BY id DESC").fetchall()
    return page("""
    <h1>Admin Panel</h1><p><a href="/logout">Logout</a></p>
    <div class="panel"><h2>Change background image</h2>
    <form action="/admin/background" method="post" enctype="multipart/form-data">
    <input type="file" name="image" accept="image/*" required>
    <button class="btn">Save background</button></form></div>

    <div class="panel"><h2>Add category</h2>
    <form action="/admin/category" method="post" enctype="multipart/form-data">
    <label>English title<input name="title" required></label>
    <label>Description<input name="description"></label>
    <label>Card image<input type="file" name="image" accept="image/*"></label>
    <button class="btn">Add category</button></form>
    {% for x in cats %}
    <p>{{x.title}} — <a href="/admin/category/delete/{{x.id}}">Delete</a></p>
    {% endfor %}</div>

    <div class="panel"><h2>Add film to a category</h2>
    <form action="/admin/film" method="post" enctype="multipart/form-data">
    <label>Category<select name="category_id">
    {% for x in cats %}<option value="{{x.id}}">{{x.title}}</option>{% endfor %}
    </select></label>
    <label>Film title<input name="title" required></label>
    <label>Description<input name="description"></label>
    <label>Poster image<input type="file" name="poster" accept="image/*"></label>
    <label>Video link<input name="video_url" placeholder="https://..."></label>
    <button class="btn">Add film</button></form>
    {% for f in films %}
    <p>{{f.title}} — <a href="/admin/film/delete/{{f.id}}">Delete</a></p>
    {% endfor %}</div>

    <div class="panel"><h2>Add option and price</h2>
    <form action="/admin/option" method="post">
    <label>Option name<input name="title" required></label>
    <label>Price in Toman<input name="price" type="number" min="0" required></label>
    <button class="btn">Add option</button></form>
    {% for x in opts %}
    <p>{{x.title}} — {{x.price}} Toman
    <a href="/admin/option/delete/{{x.id}}">Delete</a></p>
    {% endfor %}</div>

    <h2>Orders</h2>
    {% for o in orders %}
    <article class="panel order"><h3>Order #{{o.id}} — {{o.customer}}</h3>
    <p>{{o.telegram}} | {{o.total}} Toman</p><p>{{o.details}}</p>
    <a href="/private/{{o.image}}" target="_blank">View private reference image</a>
    <p>Status: {{o.status}}</p>
    <form method="post" action="/admin/order/{{o.id}}">
    <select name="status">
    {% for s in ['در انتظار پرداخت','پرداخت تأیید شد','در حال آماده‌سازی','تکمیل‌شده','لغوشده'] %}
    <option {% if o.status==s %}selected{% endif %}>{{s}}</option>
    {% endfor %}
    </select><button class="btn">Save status</button></form>
    </article>
    {% endfor %}
    """, cats=cats, opts=opts, orders=orders, films=films)

@app.route("/admin/background", methods=["POST"])
@admin_required
def background():
    name = upload_image(request.files.get("image"))
    if name is None:
        flash("Invalid image format.")
    elif name:
        save_setting("background", name)
        flash("Background updated.")
    return redirect("/admin")

@app.route("/admin/category", methods=["POST"])
@admin_required
def add_category():
    title = request.form.get("title", "").strip()
    desc = request.form.get("description", "").strip()
    name = upload_image(request.files.get("image"))
    if name is None:
        flash("Invalid image format.")
        return redirect("/admin")
    with connect() as c:
        c.execute(
            "INSERT INTO categories(title,description,image) VALUES(?,?,?)",
            (title, desc, name or "")
        )
    return redirect("/admin")

@app.route("/admin/category/delete/<int:cid>")
@admin_required
def delete_category(cid):
    with connect() as c:
        c.execute("DELETE FROM categories WHERE id=?", (cid,))
        c.execute("DELETE FROM films WHERE category_id=?", (cid,))
    return redirect("/admin")

@app.route("/admin/film", methods=["POST"])
@admin_required
def add_film():
    title = request.form.get("title", "").strip()
    desc = request.form.get("description", "").strip()
    url = request.form.get("video_url", "").strip()
    try:
        cid = int(request.form.get("category_id", "0"))
    except ValueError:
        return "Invalid category", 400
    if url and not url.startswith(("https://", "http://")):
        return "Invalid video link", 400
    poster = upload_image(request.files.get("poster"))
    if poster is None:
        flash("Invalid poster image.")
        return redirect("/admin")
    with connect() as c:
        c.execute("""INSERT INTO films
        (category_id,title,description,poster,video_url)
        VALUES(?,?,?,?,?)""", (cid, title, desc, poster or "", url))
    return redirect("/admin")

@app.route("/admin/film/delete/<int:fid>")
@admin_required
def delete_film(fid):
    with connect() as c:
        c.execute("DELETE FROM films WHERE id=?", (fid,))
    return redirect("/admin")

@app.route("/admin/option", methods=["POST"])
@admin_required
def add_option():
    title = request.form.get("title", "").strip()
    try:
        price = max(0, int(request.form.get("price", "0")))
    except ValueError:
        price = 0
    with connect() as c:
        c.execute("INSERT INTO options(title,price) VALUES(?,?)", (title, price))
    return redirect("/admin")

@app.route("/admin/option/delete/<int:oid>")
@admin_required
def delete_option(oid):
    with connect() as c:
        c.execute("DELETE FROM options WHERE id=?", (oid,))
    return redirect("/admin")

@app.route("/admin/order/<int:oid>", methods=["POST"])
@admin_required
def update_order(oid):
    status = request.form.get("status", "در انتظار پرداخت")
    allowed = ["در انتظار پرداخت", "پرداخت تأیید شد",
               "در حال آماده‌سازی", "تکمیل‌شده", "لغوشده"]
    if status not in allowed:
        return "Invalid status", 400
    with connect() as c:
        c.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    return redirect("/admin")

@app.route("/private/<path:name>")
@admin_required
def private_file(name):
    return send_from_directory(PRIVATE, name)

@app.route("/media/<path:name>")
def media(name):
    return send_from_directory(UPLOADS, name)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
