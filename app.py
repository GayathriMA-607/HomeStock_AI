import os, sqlite3, uuid, json, re
from datetime import date, datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, send_from_directory
from dotenv import load_dotenv
from PIL import Image

load_dotenv()
BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "homestock.db")
UPLOAD_DIR = os.path.join(BASE, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-this-secret")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
CATEGORIES = [
    "Pantry & Kitchen", "Stationery & Daily-use", "Cleaning & Sanitation",
    "Bathroom & Personal Care", "Refrigerator & Freezer", "Household Utilities"
]
FOOD_CATEGORY = "Refrigerator & Freezer"

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
          email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS items(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          name TEXT NOT NULL, category TEXT NOT NULL, quantity REAL NOT NULL DEFAULT 1,
          unit TEXT DEFAULT 'pcs', minimum_stock REAL DEFAULT 1, date_stocked TEXT,
          expiry_date TEXT, location TEXT DEFAULT '', price REAL DEFAULT 0,
          notes TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS transactions(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, item_id INTEGER NOT NULL,
          kind TEXT NOT NULL, amount REAL NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(item_id) REFERENCES items(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS shopping(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL,
          category TEXT DEFAULT '', quantity REAL DEFAULT 1, unit TEXT DEFAULT 'pcs',
          reason TEXT DEFAULT 'Added manually', done INTEGER DEFAULT 0,
          UNIQUE(user_id,name COLLATE NOCASE));
        CREATE TABLE IF NOT EXISTS chats(
          id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
          role TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
        # Optional profile photo column
        user_columns = [
        row["name"] for row in c.execute("PRAGMA table_info(users)").fetchall()
        ]

        if "profile_photo" not in user_columns:
            c.execute("ALTER TABLE users ADD COLUMN profile_photo TEXT")
        # Small sample recipe collection is local and does not require an external AI key.
        c.execute("""CREATE TABLE IF NOT EXISTS recipes(
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, cuisine TEXT, minutes INTEGER,
          ingredients TEXT, steps TEXT, image TEXT)""")
        if c.execute("SELECT COUNT(*) FROM recipes").fetchone()[0] == 0:
            recipes = [
              ("Vegetable Fried Rice","Asian",25,"rice,carrot,onion,peas","Cook rice. Saute vegetables. Add rice and season to taste.",""),
              ("Tomato Potato Curry","Indian",30,"tomato,potato,onion","Cook onion and tomato with spices. Add potato and simmer until tender.",""),
              ("Garden Vegetable Soup","Continental",25,"carrot,potato,onion,tomato","Simmer chopped vegetables in water or stock until tender. Season and serve.",""),
              ("Simple Omelette","Breakfast",10,"egg,onion,tomato","Beat eggs. Add chopped vegetables. Cook gently in a pan.",""),
              ("Banana Oat Bowl","Breakfast",5,"banana,oats,milk","Combine oats and milk. Top with sliced banana.","")
            ]
            c.executemany("INSERT INTO recipes(name,cuisine,minutes,ingredients,steps,image) VALUES(?,?,?,?,?,?)", recipes)

def login_required(fn):
    @wraps(fn)
    def wrapped(*a, **kw):
        if not session.get("uid"):
            if request.path.startswith("/api/"): return jsonify(error="Please log in to continue."), 401
            return redirect(url_for("login"))
        return fn(*a, **kw)
    return wrapped

def owned_item(c, item_id):
    return c.execute("SELECT * FROM items WHERE id=? AND user_id=?", (item_id, session["uid"])).fetchone()

def rowdict(r): return dict(r) if r else None

def reminders(c, uid):
    today = date.today()
    rows = c.execute("SELECT * FROM items WHERE user_id=?", (uid,)).fetchall()
    result = []
    for x in rows:
        if x["quantity"] <= x["minimum_stock"]:
            result.append({"type":"low","item":x["name"],"message":f'{x["name"]} is running low ({x["quantity"]:g} {x["unit"]} left).'})
        if x["expiry_date"]:
            try:
                days = (date.fromisoformat(x["expiry_date"]) - today).days
                if 0 <= days <= 5:
                    result.append({"type":"expiry","item":x["name"],"message":f'{x["name"]} reaches its recorded date in {days} day(s).'})
                elif days < 0:
                    result.append({"type":"expired","item":x["name"],"message":f'{x["name"]} is past its recorded date. Check the package and use reliable food-safety guidance.'})
            except ValueError: pass
    return result

@app.route("/")
def home():
    return redirect(url_for("dashboard") if session.get("uid") else url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        with db() as c: user = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], request.form.get("password","")):
            session.clear(); session["uid"] = user["id"]; session["name"] = user["name"]
            return redirect(url_for("dashboard"))
        flash("Email or password is incorrect.", "error")
    return render_template("auth.html", mode="login")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        name=request.form.get("name","").strip(); email=request.form.get("email","").strip().lower(); pw=request.form.get("password","")
        if not name or not email or len(pw)<8:
            flash("Enter your name, a valid email and a password of at least 8 characters.", "error")
        else:
            try:
                with db() as c: c.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",(name,email,generate_password_hash(pw)))
                flash("Account created. Please sign in.", "success"); return redirect(url_for("login"))
            except sqlite3.IntegrityError: flash("That email is already registered.", "error")
    return render_template("auth.html", mode="register")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/app")
@login_required
def dashboard():
    return render_template("index.html", user=session.get("name","Home member"), categories=CATEGORIES)

@app.get("/api/profile")
@login_required
def get_profile():
    """Return the signed-in user's registration details and inventory totals."""
    uid = session["uid"]

    with db() as c:
        user = c.execute(
            "SELECT id, name, email, created_at, profile_photo FROM users WHERE id = ?",
            (uid,)
        ).fetchone()

        if user is None:
            return jsonify(error="User not found."), 404

        totals = c.execute(
            """SELECT COUNT(*) AS total_items,
                      COALESCE(SUM(quantity), 0) AS total_quantity,
                      COUNT(DISTINCT category) AS categories_used
               FROM items
               WHERE user_id = ?""",
            (uid,)
        ).fetchone()

    photo_url = None
    if user["profile_photo"]:
        photo_url = url_for("profile_photo", filename=user["profile_photo"])

    return jsonify({
        "name": user["name"],
        "email": user["email"],
        "created_at": user["created_at"],
        "profile_photo_url": photo_url,
        "total_items": totals["total_items"],
        "total_quantity": totals["total_quantity"],
        "categories_used": totals["categories_used"]
    })


@app.post("/api/profile/photo")
@login_required
def upload_profile_photo():
    """Validate, resize and save an optional profile image for this user."""
    file = request.files.get("photo")
    if not file or not file.filename:
        return jsonify(error="Please select an image."), 400

    try:
        image = Image.open(file.stream)
        image.verify()
        file.stream.seek(0)
        image = Image.open(file.stream).convert("RGB")
        image.thumbnail((500, 500))
    except Exception:
        return jsonify(error="The selected file is not a valid image."), 400

    # Always save as JPEG so the filename extension and actual image format match.
    filename = f"profile_{session['uid']}_{uuid.uuid4().hex}.jpg"
    filepath = os.path.join(UPLOAD_DIR, filename)
    try:
        image.save(filepath, format="JPEG", quality=88, optimize=True)
    except Exception:
        return jsonify(error="Could not save the profile photo."), 500

    with db() as c:
        old = c.execute(
            "SELECT profile_photo FROM users WHERE id = ?",
            (session["uid"],)
        ).fetchone()
        c.execute(
            "UPDATE users SET profile_photo = ? WHERE id = ?",
            (filename, session["uid"])
        )

    if old and old["profile_photo"]:
        old_path = os.path.join(UPLOAD_DIR, old["profile_photo"])
        if os.path.isfile(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    return jsonify(
        success=True,
        photo_url=url_for("profile_photo", filename=filename)
    )


@app.get("/uploads/<filename>")
@login_required
def profile_photo(filename):
    # A user can only retrieve a profile image whose filename belongs to them.
    expected_prefix = f"profile_{session['uid']}_"
    if not filename.startswith(expected_prefix):
        return "Forbidden", 403
    return send_from_directory(UPLOAD_DIR, filename, conditional=True)


@app.delete("/api/profile/photo")
@login_required
def remove_profile_photo():
    """Remove the signed-in user's profile photo."""

    uid = session["uid"]

    # Get the currently saved photo filename
    with db() as c:
        user = c.execute(
            "SELECT profile_photo FROM users WHERE id = ?",
            (uid,)
        ).fetchone()

        if user is None:
            return jsonify(error="User not found."), 404

        old_photo = user["profile_photo"]

        # Clear the photo reference in the database
        c.execute(
            "UPDATE users SET profile_photo = NULL WHERE id = ?",
            (uid,)
        )

    # Delete the actual image file
    if old_photo:
        expected_prefix = f"profile_{uid}_"

        # Ensure the filename belongs to this user
        if old_photo.startswith(expected_prefix):
            old_path = os.path.join(UPLOAD_DIR, old_photo)

            if os.path.isfile(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    return jsonify(
                        error="Photo reference removed, but the image file could not be deleted."
                    ), 500

    return jsonify(
        success=True,
        message="Profile photo removed successfully."
    )


@app.get("/api/overview")
@login_required
def overview():
    with db() as c:
        items=c.execute("SELECT * FROM items WHERE user_id=? ORDER BY name",(session["uid"],)).fetchall()
        total=sum(x["quantity"] for x in items)
        low=[x for x in items if x["quantity"]<=x["minimum_stock"]]
        exp=reminders(c,session["uid"])
        cats=[]
        for cat in CATEGORIES:
            cats.append({"name":cat,"count":sum(1 for x in items if x["category"]==cat)})
        recent=c.execute("SELECT t.*,i.name FROM transactions t JOIN items i ON i.id=t.item_id WHERE t.user_id=? ORDER BY t.id DESC LIMIT 6",(session["uid"],)).fetchall()
        shopping=c.execute("SELECT COUNT(*) FROM shopping WHERE user_id=? AND done=0",(session["uid"],)).fetchone()[0]
        return jsonify(total_items=len(items),total_units=total,low_stock=len(low),alerts=exp[:6],categories=cats,
                       recent=[dict(x) for x in recent],shopping_count=shopping,items=[dict(x) for x in items])

@app.route("/api/inventory", methods=["GET","POST"])
@login_required
def inventory():
    if request.method=="GET":
        with db() as c:
            rows=c.execute("SELECT * FROM items WHERE user_id=? ORDER BY id DESC",(session["uid"],)).fetchall()
            return jsonify([dict(x) for x in rows])
    data=request.get_json(force=True)
    name=str(data.get("name","")).strip(); cat=data.get("category","")
    if not name or cat not in CATEGORIES: return jsonify(error="Enter an item name and choose a valid category."),400
    try:
        qty=float(data.get("quantity",1)); minimum=float(data.get("minimum_stock",1)); price=float(data.get("price",0) or 0)
        if qty<0 or minimum<0 or price<0: raise ValueError()
    except (ValueError,TypeError): return jsonify(error="Quantity, minimum stock and price must be non-negative numbers."),400
    expiry=data.get("expiry_date") or None
    if expiry:
        try: date.fromisoformat(expiry)
        except ValueError: return jsonify(error="Expiry date is invalid."),400
    with db() as c:
        cur=c.execute("""INSERT INTO items(user_id,name,category,quantity,unit,minimum_stock,date_stocked,expiry_date,location,price,notes)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(session["uid"],name,cat,qty,data.get("unit","pcs"),minimum,data.get("date_stocked") or date.today().isoformat(),expiry,data.get("location",""),price,data.get("notes","")))
        c.execute("INSERT INTO transactions(user_id,item_id,kind,amount) VALUES(?,?,?,?)",(session["uid"],cur.lastrowid,"added",qty))
        return jsonify(id=cur.lastrowid,message="Item added.")

@app.route("/api/inventory/<int:item_id>", methods=["PUT","DELETE"])
@login_required
def inventory_item(item_id):
    with db() as c:
        item=owned_item(c,item_id)
        if not item: return jsonify(error="Item not found."),404
        if request.method=="DELETE":
            c.execute("DELETE FROM items WHERE id=? AND user_id=?",(item_id,session["uid"]))
            return jsonify(message="Item removed.")
        d=request.get_json(force=True)
        name=str(d.get("name",item["name"])).strip(); cat=d.get("category",item["category"])
        if not name or cat not in CATEGORIES: return jsonify(error="Invalid item name or category."),400
        try:
            qty=float(d.get("quantity",item["quantity"])); minimum=float(d.get("minimum_stock",item["minimum_stock"]))
            if qty<0 or minimum<0: raise ValueError()
        except ValueError: return jsonify(error="Quantity values must be non-negative."),400
        expiry=d.get("expiry_date") or None
        if expiry:
            try: date.fromisoformat(expiry)
            except ValueError: return jsonify(error="Expiry date is invalid."),400
        c.execute("""UPDATE items SET name=?,category=?,quantity=?,unit=?,minimum_stock=?,date_stocked=?,expiry_date=?,location=?,price=?,notes=? WHERE id=? AND user_id=?""",
          (name,cat,qty,d.get("unit",item["unit"]),minimum,d.get("date_stocked") or item["date_stocked"],expiry,d.get("location",item["location"]),float(d.get("price",item["price"]) or 0),d.get("notes",item["notes"]),item_id,session["uid"]))
        if qty != item["quantity"]:
            c.execute("INSERT INTO transactions(user_id,item_id,kind,amount) VALUES(?,?,?,?)",(session["uid"],item_id,"adjusted",abs(qty-item["quantity"])))
        return jsonify(message="Item updated.")

@app.post("/api/inventory/<int:item_id>/consume")
@login_required
def consume(item_id):
    d=request.get_json(force=True)
    try: amount=float(d.get("amount",1))
    except: return jsonify(error="Enter a valid amount."),400
    with db() as c:
        x=owned_item(c,item_id)
        if not x: return jsonify(error="Item not found."),404
        if amount<=0 or amount>x["quantity"]: return jsonify(error="Amount must be positive and cannot exceed current stock."),400
        c.execute("UPDATE items SET quantity=quantity-? WHERE id=?",(amount,item_id))
        c.execute("INSERT INTO transactions(user_id,item_id,kind,amount) VALUES(?,?,?,?)",(session["uid"],item_id,"consumed",amount))
    return jsonify(message="Stock usage recorded.")

@app.get("/api/alerts")
@login_required
def alerts():
    with db() as c: return jsonify(reminders(c,session["uid"]))

@app.get("/api/shopping")
@login_required
def get_shopping():
    with db() as c:
        return jsonify([dict(x) for x in c.execute("SELECT * FROM shopping WHERE user_id=? ORDER BY done,id DESC",(session["uid"],)).fetchall()])

@app.post("/api/shopping")
@login_required
def add_shopping():
    d=request.get_json(force=True); name=str(d.get("name","")).strip()
    if not name:return jsonify(error="Enter a product name."),400
    with db() as c:
        c.execute("INSERT INTO shopping(user_id,name,category,quantity,unit,reason) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,name) DO UPDATE SET quantity=excluded.quantity,done=0",
          (session["uid"],name,d.get("category",""),float(d.get("quantity",1)),d.get("unit","pcs"),d.get("reason","Added manually")))
    return jsonify(message="Shopping item saved.")

@app.put("/api/shopping/<int:sid>")
@login_required
def update_shopping(sid):
    d=request.get_json(force=True)
    with db() as c:
        cur=c.execute("UPDATE shopping SET done=? WHERE id=? AND user_id=?",(1 if d.get("done") else 0,sid,session["uid"]))
        if not cur.rowcount:return jsonify(error="Shopping item not found."),404
    return jsonify(message="Updated.")

@app.delete("/api/shopping/<int:sid>")
@login_required
def delete_shopping(sid):
    with db() as c:c.execute("DELETE FROM shopping WHERE id=? AND user_id=?",(sid,session["uid"]))
    return jsonify(message="Removed.")

@app.post("/api/shopping/generate")
@login_required
def generate_shopping():
    with db() as c:
        rows=c.execute("SELECT * FROM items WHERE user_id=? AND quantity<=minimum_stock",(session["uid"],)).fetchall()
        for x in rows:
            c.execute("INSERT INTO shopping(user_id,name,category,quantity,unit,reason) VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,name) DO UPDATE SET done=0",
              (session["uid"],x["name"],x["category"],max(1,x["minimum_stock"]-x["quantity"]+1),x["unit"],"Low stock recommendation"))
    return jsonify(message=f"Checked {len(rows)} low-stock item(s).")

@app.get("/api/recipes")
@login_required
def recipes():
    with db() as c:
        inv=[x["name"].lower() for x in c.execute("SELECT name FROM items WHERE user_id=? AND category=? AND quantity>0",(session["uid"],FOOD_CATEGORY)).fetchall()]
        data=c.execute("SELECT * FROM recipes").fetchall()
    out=[]
    for r in data:
        ingredients=[x.strip() for x in r["ingredients"].split(",")]
        have=[x for x in ingredients if any(x in v or v in x for v in inv)]
        out.append({**dict(r),"ingredients_list":ingredients,"available":have,"missing":[x for x in ingredients if x not in have],"match":round(len(have)/len(ingredients)*100)})
    return jsonify(sorted(out,key=lambda x:x["match"],reverse=True))

@app.post("/api/chef-mummy")
@login_required
def chef_mummy():
    d=request.get_json(force=True); msg=str(d.get("message","")).strip()
    if not msg:return jsonify(error="Type a message first."),400
    with db() as c:
        inv=c.execute("SELECT name,quantity,unit,expiry_date FROM items WHERE user_id=? AND category=? AND quantity>0",(session["uid"],FOOD_CATEGORY)).fetchall()
        inventory=[dict(x) for x in inv]
        low=c.execute("SELECT name,quantity,unit FROM items WHERE user_id=? AND quantity<=minimum_stock",(session["uid"],)).fetchall()
        c.execute("INSERT INTO chats(user_id,role,message) VALUES(?,?,?)",(session["uid"],"user",msg))
    names=[x["name"] for x in inventory]
    q=msg.lower()
    if any(k in q for k in ["ingredient","fridge","available","what do i have"]):
        answer="Here is the food inventory currently recorded: "+(", ".join(f'{x["name"]} ({x["quantity"]:g} {x["unit"]})' for x in inventory) if inventory else "I don't see any food items yet. Add items under Refrigerator & Freezer first.")
    elif any(k in q for k in ["recipe","cook","dinner","lunch","meal"]):
        with db() as c: rs=c.execute("SELECT * FROM recipes").fetchall()
        scored=[]
        for r in rs:
            ing=[v.strip() for v in r["ingredients"].split(",")]
            score=sum(any(i in n.lower() or n.lower() in i for n in names) for i in ing)
            scored.append((score,r))
        scored.sort(key=lambda z:z[0],reverse=True)
        if scored and scored[0][0]:
            r=scored[0][1]; answer=f'Suggestion: {r["name"]} ({r["minutes"]} min). Ingredients: {r["ingredients"]}. Steps: {r["steps"]} Your recorded ingredients may not include every item; check the recipe before cooking.'
        else: answer="I need a few more refrigerator ingredients to make a useful inventory-based suggestion. Try adding vegetables, rice, eggs or dairy items."
    elif any(k in q for k in ["low stock","restock","buy","shopping"]):
        answer="These items are at or below their minimum stock: "+(", ".join(f'{x["name"]} ({x["quantity"]:g} {x["unit"]})' for x in low) if low else "none right now.")
    elif any(k in q for k in ["expiry","expire","use first"]):
        near=[x for x in inventory if x["expiry_date"]]
        answer="Recorded food dates: "+(", ".join(f'{x["name"]}: {x["expiry_date"]}' for x in near) if near else "no expiry/use-by dates have been entered. Please check package labels; I cannot determine food safety from an image.")
    else:
        answer="I'm Chef Mummy, your household kitchen helper. I can check your recorded fridge ingredients, suggest a recipe from the local recipe collection, highlight low-stock products or list recorded food dates. Ask me one of those questions!"
    with db() as c:c.execute("INSERT INTO chats(user_id,role,message) VALUES(?,?,?)",(session["uid"],"assistant",answer))
    return jsonify(reply=answer,inventory_count=len(inventory))

@app.post("/api/scanner")
@login_required
def scanner():
    f=request.files.get("image")
    if not f:return jsonify(error="Choose an image to scan."),400
    ext=os.path.splitext(secure_filename(f.filename))[1].lower()
    if ext not in [".png",".jpg",".jpeg",".webp"]:return jsonify(error="Upload a JPG, PNG or WEBP image."),400
    filename=f"{uuid.uuid4().hex}{ext}"; path=os.path.join(UPLOAD_DIR,filename); f.save(path)
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im: width,height=im.size
    except Exception:
        os.remove(path); return jsonify(error="The uploaded file is not a valid image."),400
    # Optional YOLO can be enabled by installing ultralytics and placing a custom model at models/best.pt.
    # COCO's generic labels do not reliably identify exact packaged household products, so never auto-save.
    detections=[]
    try:
        from ultralytics import YOLO
        model_path=os.path.join(BASE,"models","best.pt")
        if os.path.exists(model_path):
            model=YOLO(model_path)
            result=model(path,conf=0.25,verbose=False)[0]
            for box in result.boxes:
                label=model.names[int(box.cls[0])]
                detections.append({"name":label.title(),"category":guess_category(label),"quantity":1,"confidence":round(float(box.conf[0]),2)})
    except Exception:
        pass
    if not detections:
        detections=[{"name":"Unidentified household item","category":"Pantry & Kitchen","quantity":1,"confidence":0.0}]
    return jsonify(filename=filename,width=width,height=height,detections=detections,
      note="AI detections are suggestions only. Review every row and confirm manually. Exact product recognition requires a suitable custom-trained model.")

def guess_category(name):
    n=name.lower()
    if any(x in n for x in ["soap","shampoo","tooth","cream"]): return "Bathroom & Personal Care"
    if any(x in n for x in ["detergent","cleaner","brush"]): return "Cleaning & Sanitation"
    if any(x in n for x in ["food","fruit","vegetable","milk","egg"]): return FOOD_CATEGORY
    if any(x in n for x in ["book","pen","paper"]): return "Stationery & Daily-use"
    return "Pantry & Kitchen"

@app.post("/api/scanner/confirm")
@login_required
def scanner_confirm():
    d=request.get_json(force=True); rows=d.get("items",[])
    if not rows:return jsonify(error="No reviewed items to add."),400
    added=0
    with db() as c:
        for x in rows:
            name=str(x.get("name","")).strip(); cat=x.get("category")
            if not name or cat not in CATEGORIES:continue
            qty=max(0,float(x.get("quantity",1)))
            expiry=x.get("expiry_date") or None
            if expiry:
                try:date.fromisoformat(expiry)
                except ValueError:continue
            cur=c.execute("INSERT INTO items(user_id,name,category,quantity,unit,minimum_stock,date_stocked,expiry_date) VALUES(?,?,?,?,?,?,?,?)",
              (session["uid"],name,cat,qty,x.get("unit","pcs"),float(x.get("minimum_stock",1)),date.today().isoformat(),expiry))
            c.execute("INSERT INTO transactions(user_id,item_id,kind,amount) VALUES(?,?,?,?)",(session["uid"],cur.lastrowid,"scanned",qty)); added+=1
    return jsonify(message=f"{added} reviewed item(s) added.")

@app.get("/api/analytics")
@login_required
def analytics():
    with db() as c:
        items=c.execute("SELECT * FROM items WHERE user_id=?",(session["uid"],)).fetchall()
        tx=c.execute("SELECT kind,amount,created_at FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 100",(session["uid"],)).fetchall()
    cats={x:sum(i["quantity"] for i in items if i["category"]==x) for x in CATEGORIES}
    spent=sum(i["price"]*i["quantity"] for i in items)
    consumed=sum(t["amount"] for t in tx if t["kind"]=="consumed")
    return jsonify(categories=cats,recorded_value=round(spent,2),consumed_units=round(consumed,2),
      low_stock=sum(1 for i in items if i["quantity"]<=i["minimum_stock"]),total=len(items),
      prediction_note="Replenishment estimates are based on recorded stock thresholds. A personalized consumption model needs several dated stock-change records.")

@app.errorhandler(413)
def too_large(e): return jsonify(error="Image is too large. Maximum upload size is 8 MB."),413

@app.errorhandler(500)
def server_error(e):
    return jsonify(error="Something went wrong. Check the Flask terminal for details."),500

init_db()
if __name__=="__main__":
    app.run(host="127.0.0.1",port=5000,debug=os.getenv("FLASK_DEBUG","1")=="1")
