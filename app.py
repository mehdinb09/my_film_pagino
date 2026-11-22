
import os
import sqlite3
import secrets
import requests
from pathlib import Path
from functools import wraps
from flask import Flask, request, redirect, session, flash, render_template_string, send_from_directory

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"
UPLOADS.mkdir(exist_ok=True)
DB = BASE / "cinema.db"

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-me-now")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")
ALLOWED = {"jpg", "jpeg", "png", "webp"}

STYLE = """
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;800;900&display=swap');
*{box-sizing:border-box}
body{margin:0;background:#08090d;color:#f5f5f5;font-family:Vazirmatn,sans-serif}
nav{padding:20px 7%;display:flex;justify-content:space-between;align-items:center;
border-bottom:1px solid #29232a;background:#0b0b10}
a{color:#fff;text-decoration:none}
.brand{font-size:21px;font-weight:900;letter-spacing:2px}
.brand span,h1 em{color:#ed3150;font-style:normal}
nav div{display:flex;gap:18px;font-size:13px}
main{padding:45px 7%;min-height:75vh}
.hero{padding:65px 5%;background:linear-gradient(110deg,#170b12,#11121a);
border:1px solid #35202a;border-radius:18px}
.hero h1{font-size:clamp(38px,8vw,68px);line-height:1.4}
p{color:#b8b8c2;line-height:2}
h2{margin-top:35px}
.btn{display:inline-block;background:#d91f40;color:white;border:0;border-radius:8px;
padding:13px 20px;font:700 14px Vazirmatn;cursor:pointer}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:17px;margin-top:25px}
.card,.panel{background:#13141b;border:1px solid #302a32;border-radius:13px;padding:18px}
.card img{width:100%;height:170px;object-fit:cover;border-radius:9px}
input,textarea,select{display:block;width:100%;padding:12px;margin:8px 0 17px;
background:#090a10;color:white;border:1px solid #444;border-radius:7px;font:inherit}
label{display:block;color:#ddd}
.option{padding:12px;border-bottom:1px solid #333;display:flex;justify-content:space-between}
.option input{width:auto;display:inline}
small{color:#aaa}
.notice{padding:12px;background:#401522;border-radius:8px;margin-bottom:15px}
footer{padding:25px 7%;border-top:1px solid #333;color:#999}
.order{padding:18px 0;border-bottom:1px solid #444}
.order img{max-width:220px;display:block;margin:12px 0;border-radius:8px}
@media(max-width:600px){nav{padding:16px 4%}nav div{gap:9px;font-size:11px}main{padding:28px 4%}}
"""

def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def setup():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,description TEXT,image TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS options(
        id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,price INTEGER)""")
        c.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,customer TEXT,telegram TEXT,
        details TEXT,total INTEGER,image TEXT,status TEXT DEFAULT 'در انتظار پرداخت')""")

setup()

def page(content, **data):
    body = render_template_string(content, **data)
    return render_template_string("""
    <!doctype html><html lang="fa" dir="rtl"><head>
    <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>BLACK CINEMA</title><style>""" + STYLE + """</style></head>
    <body><nav><a class="brand" href="/">BLACK <span>CINEMA</span></a>
    <div><a href="/">خانه</a><a href="/custom">ساخت فیلم خصوصی</a>
    <a href="/login">مدیریت</a></div></nav><main>
    {% with msgs=get_flashed_messages() %}{% for m in msgs %}
    <div class="notice">{{m}}</div>{% endfor %}{% endwith %}
    """ + body + """</main><footer>BLACK CINEMA — تجربه‌ای متفاوت</footer></body></html>""")

def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not session.get("admin"):
            return redirect("/login")
        return fn(*a, **kw)
    return wrapper

def telegram_notice(order_id, customer, username, total, details):
    if not BOT_TOKEN or not ADMIN_CHAT_ID:
        return
    message = (
        f"🎬 سفارش BLACK CINEMA #{order_id}\n"
        f"مشتری: {customer}\nتلگرام: {username}\n"
        f"مبلغ: {total:,} تومان\nجزئیات: {details}"
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
    with connect() as c:
        cats = c.execute("SELECT * FROM categories ORDER BY id DESC").fetchall()
    return page("""
    <section class="hero"><small>PRIVATE • PREMIUM • CINEMA</small>
    <h1>دنیای تصویر،<br><em>با انتخاب تو</em></h1>
    <p>مجموعه موردنظرت را انتخاب کن.</p>
    <a class="btn" href="/custom">ساخت فیلم خصوصی خود ←</a></section>
    <h2>دسته‌بندی‌ها</h2><div class="grid">
    {% for x in cats %}<a class="card" href="/category/{{x.id}}">
    {% if x.image %}<img src="/uploads/{{x.image}}">{% endif %}
    <h3>{{x.title}}</h3><p>{{x.description}}</p>مشاهده مجموعه ←</a>
    {% endfor %}
    <a class="card" href="/custom"><h3>ساخت فیلم خصوصی خود</h3>
    <p>انتخاب ویژگی‌ها و ثبت سفارش</p>شروع ←</a></div>
    """, cats=cats)

@app.route("/category/<int:cid>")
def category(cid):
    with connect() as c:
        cat = c.execute("SELECT * FROM categories WHERE id=?", (cid,)).fetchone()
    if not cat:
        return "دسته‌بندی پیدا نشد", 404
    return page("<h1>{{cat.title}}</h1><p>{{cat.description}}</p><p>محتوای این مجموعه از پنل مدیریت قابل تکمیل است.</p><a href='/'>بازگشت</a>", cat=cat)

@app.route("/custom", methods=["GET", "POST"])
def custom():
    with connect() as c:
        opts = c.execute("SELECT * FROM options ORDER BY id").fetchall()
    if request.method == "POST":
        customer = request.form.get("customer", "").strip()
        telegram = request.form.get("telegram", "").strip().lstrip("@")
        image = request.files.get("reference")
        if not customer or not telegram or not image or not image.filename:
            flash("نام، آیدی تلگرام و تصویر را وارد کن.")
            return redirect("/custom")
        ext = image.filename.rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED:
            flash("فرمت تصویر باید JPG، PNG یا WEBP باشد.")
            return redirect("/custom")
        filename = secrets.token_hex(16) + "." + ext
        image.save(UPLOADS / filename)
        chosen, total = [], 0
        with connect() as c:
            for raw in request.form.getlist("options"):
                if raw.isdigit():
                    opt = c.execute("SELECT * FROM options WHERE id=?", (int(raw),)).fetchone()
                    if opt:
                        chosen.append(f"{opt['title']} ({opt['price']:,} تومان)")
                        total += opt["price"]
            details = "، ".join(chosen) or "بدون گزینه اضافه"
            cur = c.execute("""INSERT INTO orders
            (customer,telegram,details,total,image) VALUES(?,?,?,?,?)""",
            (customer, "@" + telegram, details, total, filename))
            oid = cur.lastrowid
        telegram_notice(oid, customer, "@" + telegram, total, details)
        return page("<h1>سفارش ثبت شد</h1><h2>شماره سفارش: #{{oid}}</h2><h2>{{'{:,}'.format(total)}} تومان</h2><p>سفارش ثبت شده اما پرداخت آنلاین هنوز متصل نیست.</p>", oid=oid, total=total)
    return page("""
    <h1>ساخت فیلم خصوصی خود</h1><p>ویژگی‌ها را انتخاب کن و تصویر مرجع را بفرست.</p>
    <form class="panel" method="post" enctype="multipart/form-data">
    <label>نام<input name="customer" required></label>
    <label>آیدی تلگرام<input name="telegram" placeholder="@username" required></label>
    <h3>انتخاب ویژگی‌ها</h3>
    {% for o in opts %}<label class="option">
    <span><input type="checkbox" name="options" value="{{o.id}}">{{o.title}}</span>
    <b>{{"{:,}".format(o.price)}} تومان</b></label>{% endfor %}
    <label>تصویر مرجع<input type="file" name="reference" accept="image/*" required></label>
    <button class="btn">ثبت سفارش</button></form>
    <small>این نسخه درگاه بانکی ندارد؛ ثبت سفارش به معنی پرداخت نیست.</small>
    """, opts=opts)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USER and secrets.compare_digest(
            request.form.get("password", ""), ADMIN_PASSWORD
        ):
            session["admin"] = True
            return redirect("/admin")
        flash("نام کاربری یا رمز اشتباه است.")
    return page("""
    <h1>ورود مدیریت</h1><form class="panel" method="post">
    <label>نام کاربری<input name="username"></label>
    <label>رمز عبور<input name="password" type="password"></label>
    <button class="btn">ورود</button></form>
    """)

@app.route("/admin")
@admin_required
def admin():
    with connect() as c:
        cats = c.execute("SELECT * FROM categories ORDER BY id DESC").fetchall()
        opts = c.execute("SELECT * FROM options ORDER BY id DESC").fetchall()
        orders = c.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    return page("""
    <h1>پنل مدیریت</h1><p><a href="/logout">خروج</a></p>
    <div class="grid"><section class="panel"><h2>افزودن دسته‌بندی</h2>
    <form action="/admin/category" method="post" enctype="multipart/form-data">
    <label>عنوان<input name="title" required></label>
    <label>توضیح<input name="description"></label>
    <label>تصویر<input type="file" name="image" accept="image/*"></label>
    <button class="btn">افزودن</button></form>
    {% for x in cats %}<p>{{x.title}} <a href="/admin/category/delete/{{x.id}}">حذف</a></p>{% endfor %}
    </section><section class="panel"><h2>افزودن گزینه و قیمت</h2>
    <form action="/admin/option" method="post">
    <label>نام گزینه<input name="title" required></label>
    <label>قیمت تومان<input name="price" type="number" min="0" required></label>
    <button class="btn">افزودن</button></form>
    {% for x in opts %}<p>{{x.title}} — {{x.price}} تومان <a href="/admin/option/delete/{{x.id}}">حذف</a></p>{% endfor %}
    </section></div><h2>سفارش‌ها</h2>
    {% for o in orders %}<article class="order"><h3>سفارش #{{o.id}} — {{o.customer}}</h3>
    <p>{{o.telegram}} | {{o.total}} تومان</p><p>{{o.details}}</p>
    <img src="/uploads/{{o.image}}"><p>وضعیت: {{o.status}}</p>
    <form method="post" action="/admin/order/{{o.id}}">
    <select name="status">{% for s in ['در انتظار پرداخت','پرداخت تأیید شد','در حال آماده‌سازی','تکمیل‌شده','لغوشده'] %}
    <option {% if o.status==s %}selected{% endif %}>{{s}}</option>{% endfor %}</select>
    <button class="btn">ذخیره وضعیت</button></form></article>{% endfor %}
    """, cats=cats, opts=opts, orders=orders)

@app.route("/admin/category", methods=["POST"])
@admin_required
def add_category():
    title = request.form.get("title", "").strip()
    desc = request.form.get("description", "").strip()
    image = request.files.get("image")
    filename = ""
    if image and image.filename:
        ext = image.filename.rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED:
            flash("فرمت تصویر معتبر نیست.")
            return redirect("/admin")
        filename = secrets.token_hex(16) + "." + ext
        image.save(UPLOADS / filename)
    with connect() as c:
        c.execute("INSERT INTO categories(title,description,image) VALUES(?,?,?)", (title, desc, filename))
    return redirect("/admin")

@app.route("/admin/category/delete/<int:cid>")
@admin_required
def delete_category(cid):
    with connect() as c:
        c.execute("DELETE FROM categories WHERE id=?", (cid,))
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
    allowed = ["در انتظار پرداخت", "پرداخت تأیید شد", "در حال آماده‌سازی", "تکمیل‌شده", "لغوشده"]
    if status not in allowed:
        return "وضعیت نامعتبر", 400
    with connect() as c:
        c.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    return redirect("/admin")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/uploads/<path:name>")
@admin_required
def uploads(name):
    return send_from_directory(UPLOADS, name)

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
