"""Digi Bus Pass Flask application with SQLite persistence."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

ROOT = Path(__file__).resolve().parent
INSTANCE = Path(os.environ.get("INSTANCE_DIR", ROOT / "instance"))
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", INSTANCE / "uploads"))
PRIVATE_UPLOAD_DIR = Path(os.environ.get("PRIVATE_UPLOAD_DIR", INSTANCE / "private_uploads"))
DB_PATH = Path(os.environ.get("DATABASE_PATH", INSTANCE / "digibuspass.sqlite3"))
INSTANCE.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PRIVATE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder=None)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

FIELDS = [
    "full_name", "guardian_name", "dob", "gender", "aadhaar_number",
    "mobile_number", "email", "address", "city", "state", "pincode",
    "pass_category", "other_category", "pass_type", "start_date", "end_date",
    "route_number", "source_location", "destination_location", "timing",
    "route_details", "starting_bus_stop", "ending_bus_stop",
    "preferred_travel_route", "validity_period", "payment_method", "amount",
    "aadhaar_doc", "photo",
]


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS personal_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL, guardian_name TEXT, dob TEXT, gender TEXT,
            aadhaar_number TEXT, mobile_number TEXT NOT NULL, email TEXT,
            address TEXT, city TEXT, state TEXT, pincode TEXT,
            pass_category TEXT, other_category TEXT, pass_type TEXT,
            start_date TEXT, end_date TEXT, route_number TEXT, source_location TEXT,
            destination_location TEXT, timing TEXT, route_details TEXT,
            starting_bus_stop TEXT, ending_bus_stop TEXT, preferred_travel_route TEXT,
            validity_period TEXT, payment_method TEXT, amount REAL,
            payment_status TEXT NOT NULL DEFAULT 'pending', payment_reference TEXT,
            aadhaar_doc TEXT, photo TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE, password TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS conductors (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS payment_orders (
            order_id TEXT PRIMARY KEY, amount INTEGER NOT NULL, currency TEXT NOT NULL,
            status TEXT NOT NULL, payment_id TEXT
        );
        """)
        conductor_name = os.environ.get("CONDUCTOR_USERNAME")
        conductor_password = os.environ.get("CONDUCTOR_PASSWORD")
        if conductor_name and conductor_password:
            hashed = generate_password_hash(conductor_password)
            db.execute("INSERT INTO conductors(username,password) VALUES(?,?) "
                       "ON CONFLICT(username) DO UPDATE SET password=excluded.password",
                       (conductor_name, hashed))


init_db()


def json_error(message, status=400):
    return jsonify(status="error", message=message), status


def save_upload(field):
    upload = request.files.get(field)
    if not upload or not upload.filename:
        return ""
    name = secure_filename(upload.filename)
    ext = Path(name).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".pdf"}:
        raise ValueError(f"Unsupported {field} file type")
    filename = f"{uuid.uuid4().hex}{ext}"
    target_dir = PRIVATE_UPLOAD_DIR if field == "aadhaar_doc" else UPLOAD_DIR
    upload.save(target_dir / filename)
    if field == "aadhaar_doc":
        return filename
    return f"/uploads/{filename}"


def public_pass(row):
    data = dict(row)
    # Identity documents and Aadhaar numbers must never be exposed by pass lookup.
    data.pop("aadhaar_doc", None)
    data.pop("aadhaar_number", None)
    return data


def razorpay_configured():
    return bool(os.environ.get("RAZORPAY_KEY_ID") and os.environ.get("RAZORPAY_KEY_SECRET"))


@app.get("/")
def home():
    return send_from_directory(ROOT, "index.html")


@app.get("/<path:filename>")
def static_files(filename):
    # PHP sources are intentionally replaced by Flask handlers below.
    if filename.lower().endswith(".php"):
        return json_error("Endpoint not found", 404)
    return send_from_directory(ROOT, filename)


@app.get("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/save_combined_data.php", methods=["POST"])
def save_combined_data():
    values = {key: request.form.get(key, "").strip() for key in FIELDS if key not in {"photo", "aadhaar_doc"}}
    if not values.get("full_name") or not values.get("mobile_number"):
        return json_error("Full name and mobile number are required")
    method = values.get("payment_method", "").lower()
    payment_id = request.form.get("razorpay_payment_id", "")
    if method != "cash":
        if not payment_id:
            return json_error("Complete payment before submitting the pass application", 402)
        with connect() as db:
            payment = db.execute("SELECT status,amount FROM payment_orders WHERE payment_id=?", (payment_id,)).fetchone()
        try:
            submitted_amount = round(float(values.get("amount") or 0) * 100)
        except ValueError:
            return json_error("Enter a valid payment amount")
        if not payment or payment["status"] != "paid" or payment["amount"] != submitted_amount:
            return json_error("Payment could not be verified for this amount", 402)
    elif method == "cash":
        return json_error("Cash payment requires in-person verification and cannot create a digital pass", 402)
    try:
        values["photo"] = save_upload("photo")
        values["aadhaar_doc"] = save_upload("aadhaar_doc")
        amount = float(values.get("amount") or 0)
        if amount < 0 or amount > 100000:
            return json_error("Invalid pass amount")
    except (ValueError, OSError) as exc:
        return json_error(str(exc))
    values["amount"] = amount
    names = ",".join(FIELDS)
    marks = ",".join("?" for _ in FIELDS)
    with connect() as db:
        if method != "cash":
            claimed = db.execute("UPDATE payment_orders SET status='claimed' WHERE payment_id=? AND status='paid'", (payment_id,))
            if not claimed.rowcount:
                return json_error("This payment was already used for an application", 409)
        cur = db.execute(f"INSERT INTO personal_details ({names},payment_status,payment_reference) VALUES ({marks},?,?)",
                         [values[k] for k in FIELDS] + ["paid" if method != "cash" else "pending", payment_id or None])
        pass_id = cur.lastrowid
    return jsonify(status="success", message="Pass application saved", id=pass_id)


@app.route("/api/payment/order", methods=["POST"])
def create_payment_order():
    if not razorpay_configured():
        return json_error("Online payments are not configured. Set Razorpay test/live keys in the hosting environment.", 503)
    body = request.get_json(silent=True) or {}
    try:
        amount = round(float(body.get("amount", 0)) * 100)
    except (TypeError, ValueError):
        return json_error("Enter a valid payment amount")
    if amount < 100 or amount > 10000000:
        return json_error("Payment amount must be between ₹1 and ₹100,000")
    import urllib.request
    payload = json.dumps({"amount": amount, "currency": "INR", "receipt": f"pass_{secrets.token_hex(8)}"}).encode()
    token = (os.environ["RAZORPAY_KEY_ID"] + ":" + os.environ["RAZORPAY_KEY_SECRET"]).encode()
    req = urllib.request.Request("https://api.razorpay.com/v1/orders", data=payload,
        headers={"Authorization": "Basic " + __import__("base64").b64encode(token).decode(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            order = json.loads(response.read())
    except Exception:
        app.logger.exception("Razorpay order creation failed")
        return json_error("Could not start payment. Please retry.", 502)
    with connect() as db:
        db.execute("INSERT INTO payment_orders(order_id,amount,currency,status) VALUES(?,?,?,'created')",
                   (order["id"], amount, "INR"))
    return jsonify(order_id=order["id"], key_id=os.environ["RAZORPAY_KEY_ID"], amount=amount, currency="INR")


@app.route("/api/payment/verify", methods=["POST"])
def verify_payment():
    if not razorpay_configured():
        return json_error("Payments are not configured", 503)
    body = request.get_json(silent=True) or {}
    order_id, payment_id, signature = (body.get(k, "") for k in ("razorpay_order_id", "razorpay_payment_id", "razorpay_signature"))
    expected = hmac.new(os.environ["RAZORPAY_KEY_SECRET"].encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    if not order_id or not payment_id or not hmac.compare_digest(expected, signature):
        return json_error("Payment signature verification failed", 400)
    with connect() as db:
        result = db.execute("UPDATE payment_orders SET status='paid',payment_id=? WHERE order_id=? AND status='created'", (payment_id, order_id))
    if not result.rowcount:
        return json_error("Payment order not found or already used", 409)
    return jsonify(status="success", payment_id=payment_id)


@app.get("/get_pass_data.php")
def get_pass_data():
    pass_id = request.args.get("id", type=int)
    with connect() as db:
        row = db.execute("SELECT * FROM personal_details WHERE id=? AND payment_status IN ('paid','pending')" if pass_id else
                         "SELECT * FROM personal_details WHERE payment_status IN ('paid','pending') ORDER BY id DESC LIMIT 1",
                         (pass_id,) if pass_id else ()).fetchone()
    if not row:
        return json_error("No pass data found", 404)
    return jsonify(status="success", passData=public_pass(row))


@app.get("/fetch_pass.php")
@app.get("/fetchbuspass.php")
def fetch_pass():
    with connect() as db:
        row = db.execute("SELECT * FROM personal_details WHERE payment_status IN ('paid','pending') ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return json_error("No pass data found", 404)
    data = public_pass(row)
    data["name"] = data.get("full_name")
    data["validity"] = f"{data.get('start_date','')} to {data.get('end_date','')}"
    data["route"] = f"{data.get('route_number','')} ({data.get('source_location','')} to {data.get('destination_location','')})"
    return jsonify(data)


@app.get("/get_pass/<int:pass_id>")
def legacy_get_pass(pass_id):
    with connect() as db:
        row = db.execute("SELECT * FROM personal_details WHERE id=?", (pass_id,)).fetchone()
    return (jsonify(public_pass(row)), 200) if row else json_error("Pass not found", 404)


@app.get("/get_routes.php")
def get_routes():
    with connect() as db:
        rows = db.execute("SELECT DISTINCT route_number,source_location,destination_location FROM personal_details WHERE route_number<>'' ORDER BY route_number").fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/auth.php", methods=["POST"])
@app.route("/login.php", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    if "signup" in request.form:
        if not username or not email or len(password) < 8:
            return "Username, email and a password of at least 8 characters are required", 400
        try:
            with connect() as db:
                db.execute("INSERT INTO users(username,email,password) VALUES(?,?,?)",
                           (username, email, generate_password_hash(password)))
            session["username"] = username
            return redirect("index.html")
        except sqlite3.IntegrityError:
            return "An account with that email already exists", 409
    with connect() as db:
        user = db.execute("SELECT username,password FROM users WHERE email=?", (email or username,)).fetchone()
    if user and check_password_hash(user["password"], password):
        session["username"] = user["username"]
        return redirect("index.html")
    return "Invalid username or password", 401


@app.post("/db_connection.php")
def conductor_login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    with connect() as db:
        user = db.execute("SELECT password FROM conductors WHERE username=?", (username,)).fetchone()
    if user and check_password_hash(user["password"], password):
        session["username"] = username
        return "success"
    return "Invalid username or password", 401


@app.post("/renew_pass.php")
@app.post("/process_renewal.php")
def renew_pass():
    pass_id = request.form.get("id", type=int)
    end_date = request.form.get("end_date", "")
    if not pass_id or not end_date:
        return json_error("Pass ID and new end date are required")
    with connect() as db:
        cur = db.execute("UPDATE personal_details SET end_date=? WHERE id=?", (end_date, pass_id))
    return jsonify(status="success") if cur.rowcount else json_error("Pass not found", 404)


@app.get("/health")
def health():
    return jsonify(status="ok", database="sqlite")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
