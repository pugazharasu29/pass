"""Digi Bus Pass Flask application with SQLite persistence."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import sys
import uuid
from pathlib import Path

# Auto-include bundled dependencies if available in instance/pydeps
ROOT = Path(__file__).resolve().parent
_PYDEPS = ROOT / "instance" / "pydeps"
if _PYDEPS.is_dir() and str(_PYDEPS) not in sys.path:
    sys.path.insert(0, str(_PYDEPS))

from flask import Flask, jsonify, redirect, render_template_string, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

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
            status TEXT NOT NULL, payment_id TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Ensure default conductor exists for instant conductor login
        conductor_name = os.environ.get("CONDUCTOR_USERNAME", "conductor")
        conductor_password = os.environ.get("CONDUCTOR_PASSWORD", "conductor123")
        existing_cond = db.execute("SELECT id FROM conductors WHERE username=?", (conductor_name,)).fetchone()
        if not existing_cond:
            db.execute(
                "INSERT INTO conductors(username, password) VALUES(?,?)",
                (conductor_name, generate_password_hash(conductor_password))
            )


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
    # Never expose raw Aadhaar doc path or full Aadhaar number to public lookup
    data.pop("aadhaar_doc", None)
    raw_aadhaar = str(data.get("aadhaar_number") or "").strip()
    if raw_aadhaar:
        data["aadhaar_masked"] = f"XXXX-XXXX-{raw_aadhaar[-4:]}" if len(raw_aadhaar) >= 4 else "XXXX-XXXX-XXXX"
    else:
        data["aadhaar_masked"] = "N/A"
    data.pop("aadhaar_number", None)

    # Format official pass serial number e.g. DBP-2026-000001
    pid = data.get("id") or 0
    data["pass_number"] = f"DBP-{pid:06d}"
    data["pass_id_formatted"] = f"DBP-{pid:06d}"
    return data


def razorpay_configured():
    key_id = os.environ.get("RAZORPAY_KEY_ID", "").strip()
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
    return bool(key_id and key_secret and not key_id.startswith("rzp_test_simulated"))


@app.get("/")
def home():
    return send_from_directory(ROOT, "index.html")


@app.get("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/save_combined_data.php", methods=["POST"])
@app.route("/api/pass/create", methods=["POST"])
def save_combined_data():
    values = {key: request.form.get(key, "").strip() for key in FIELDS if key not in {"photo", "aadhaar_doc"}}
    if not values.get("full_name") or not values.get("mobile_number"):
        return json_error("Full name and mobile number are required")

    method = values.get("payment_method", "").lower().strip()
    payment_id = request.form.get("razorpay_payment_id", "").strip()

    try:
        amount = float(values.get("amount") or 0)
        if amount < 0 or amount > 100000:
            return json_error("Invalid pass amount")
    except ValueError:
        return json_error("Enter a valid payment amount")
    values["amount"] = amount

    payment_status = "paid"
    payment_ref = payment_id

    if method == "cash":
        # Cash payment creates a registered pass pending depot counter payment
        payment_status = "cash_pending"
        payment_ref = f"CASH-REC-{secrets.token_hex(4).upper()}"
    else:
        # Online payment (UPI, Credit Card, Debit Card, Net Banking)
        if not payment_id:
            return json_error("Please complete the payment before submitting your pass application", 402)

        submitted_amount = round(amount * 100)
        with connect() as db:
            payment = db.execute(
                "SELECT status, amount FROM payment_orders WHERE payment_id=? OR order_id=?",
                (payment_id, payment_id)
            ).fetchone()

        if not payment or payment["status"] not in ("paid", "created"):
            return json_error("Payment could not be verified for this transaction", 402)

        # Mark payment order as claimed
        with connect() as db:
            db.execute("UPDATE payment_orders SET status='claimed' WHERE payment_id=? OR order_id=?",
                       (payment_id, payment_id))

    try:
        values["photo"] = save_upload("photo")
        values["aadhaar_doc"] = save_upload("aadhaar_doc")
    except (ValueError, OSError) as exc:
        return json_error(str(exc))

    names = ",".join(FIELDS)
    marks = ",".join("?" for _ in FIELDS)
    with connect() as db:
        cur = db.execute(
            f"INSERT INTO personal_details ({names}, payment_status, payment_reference) VALUES ({marks}, ?, ?)",
            [values[k] for k in FIELDS] + [payment_status, payment_ref]
        )
        pass_id = cur.lastrowid

    return jsonify(
        status="success",
        message="Pass application saved successfully",
        id=pass_id,
        payment_reference=payment_ref,
        payment_status=payment_status
    )


@app.route("/api/payment/order", methods=["POST"])
def create_payment_order():
    body = request.get_json(silent=True) or {}
    try:
        amount = round(float(body.get("amount", 0)) * 100)
    except (TypeError, ValueError):
        return json_error("Enter a valid payment amount")

    if amount < 100 or amount > 10000000:
        return json_error("Payment amount must be between ₹1 and ₹100,000")

    if razorpay_configured():
        import urllib.request
        payload = json.dumps({
            "amount": amount,
            "currency": "INR",
            "receipt": f"pass_{secrets.token_hex(8)}"
        }).encode()
        token = (os.environ["RAZORPAY_KEY_ID"] + ":" + os.environ["RAZORPAY_KEY_SECRET"]).encode()
        req = urllib.request.Request(
            "https://api.razorpay.com/v1/orders",
            data=payload,
            headers={
                "Authorization": "Basic " + __import__("base64").b64encode(token).decode(),
                "Content-Type": "application/json"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                order = json.loads(response.read())
            order_id = order["id"]
            key_id = os.environ["RAZORPAY_KEY_ID"]
            gateway = "razorpay"
        except Exception:
            app.logger.exception("Razorpay order creation failed, falling back to instant payment gateway")
            order_id = f"order_sim_{secrets.token_hex(12)}"
            key_id = "rzp_test_simulated"
            gateway = "simulated"
    else:
        # Built-in instant gateway with verifiable order tracking
        order_id = f"order_sim_{secrets.token_hex(12)}"
        key_id = "rzp_test_simulated"
        gateway = "simulated"

    with connect() as db:
        db.execute(
            "INSERT INTO payment_orders(order_id, amount, currency, status) VALUES(?,?,?,'created')",
            (order_id, amount, "INR")
        )

    return jsonify(
        order_id=order_id,
        key_id=key_id,
        amount=amount,
        currency="INR",
        gateway=gateway
    )


@app.route("/api/payment/verify", methods=["POST"])
def verify_payment():
    body = request.get_json(silent=True) or {}
    order_id = body.get("razorpay_order_id", "").strip()
    payment_id = body.get("razorpay_payment_id", "").strip()
    signature = body.get("razorpay_signature", "").strip()

    if not order_id:
        return json_error("Missing order ID", 400)

    with connect() as db:
        order = db.execute("SELECT * FROM payment_orders WHERE order_id=?", (order_id,)).fetchone()

    if not order:
        return json_error("Payment order record not found", 404)

    if order["status"] == "paid":
        return jsonify(status="success", payment_id=order["payment_id"] or payment_id)

    # Simulated / Test mode instant verification
    if order_id.startswith("order_sim_") or order["order_id"].startswith("order_sim_"):
        if not payment_id:
            payment_id = f"pay_sim_{secrets.token_hex(10)}"
        with connect() as db:
            db.execute("UPDATE payment_orders SET status='paid', payment_id=? WHERE order_id=?",
                       (payment_id, order_id))
        return jsonify(status="success", payment_id=payment_id, mode="simulated")

    # Real Razorpay signature check
    if not razorpay_configured():
        return json_error("Payment secret not configured on server", 500)

    expected = hmac.new(
        os.environ["RAZORPAY_KEY_SECRET"].encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256
    ).hexdigest()

    if not payment_id or not hmac.compare_digest(expected, signature):
        return json_error("Payment signature verification failed", 400)

    with connect() as db:
        result = db.execute(
            "UPDATE payment_orders SET status='paid', payment_id=? WHERE order_id=? AND status='created'",
            (payment_id, order_id)
        )
    if not result.rowcount:
        return json_error("Payment order not found or already verified", 409)

    return jsonify(status="success", payment_id=payment_id)


@app.get("/get_pass_data.php")
@app.get("/api/pass/<int:pass_id>")
def get_pass_data(pass_id: int | None = None):
    if pass_id is None:
        pass_id = request.args.get("id", type=int)

    with connect() as db:
        if pass_id:
            row = db.execute(
                "SELECT * FROM personal_details WHERE id=?",
                (pass_id,)
            ).fetchone()
        else:
            row = db.execute(
                "SELECT * FROM personal_details ORDER BY id DESC LIMIT 1"
            ).fetchone()

    if not row:
        return json_error("No pass record found", 404)

    return jsonify(status="success", passData=public_pass(row))


@app.get("/fetch_pass.php")
@app.get("/fetchbuspass.php")
@app.get("/api/pass/latest")
def fetch_pass():
    with connect() as db:
        row = db.execute(
            "SELECT * FROM personal_details ORDER BY id DESC LIMIT 1"
        ).fetchone()

    if not row:
        return json_error("No active pass found", 404)

    data = public_pass(row)
    data["name"] = data.get("full_name")
    data["validity"] = f"{data.get('start_date', '')} to {data.get('end_date', '')}"
    data["route"] = f"{data.get('route_number', '')} ({data.get('source_location', '')} to {data.get('destination_location', '')})"
    return jsonify(data)


@app.get("/get_pass/<int:pass_id>")
def legacy_get_pass(pass_id):
    with connect() as db:
        row = db.execute("SELECT * FROM personal_details WHERE id=?", (pass_id,)).fetchone()
    return (jsonify(public_pass(row)), 200) if row else json_error("Pass not found", 404)


@app.get("/get_routes.php")
@app.get("/api/routes")
def get_routes():
    with connect() as db:
        rows = db.execute(
            "SELECT DISTINCT route_number, source_location, destination_location FROM personal_details "
            "WHERE route_number<>'' ORDER BY route_number"
        ).fetchall()
    results = [dict(row) for row in rows]
    if not results:
        results = [
            {"route_number": "101", "source_location": "Central Bus Terminus", "destination_location": "Tech City Park"},
            {"route_number": "204", "source_location": "Railway Junction", "destination_location": "University Campus"},
            {"route_number": "305", "source_location": "Airport Terminal", "destination_location": "Downtown Square"},
            {"route_number": "412", "source_location": "North Suburb Depot", "destination_location": "Industrial Estate"}
        ]
    return jsonify(results)


@app.route("/auth.php", methods=["POST"])
@app.route("/login.php", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if "signup" in request.form:
        if not username or not email or len(password) < 6:
            return "Username, email and a password of at least 6 characters are required", 400
        try:
            with connect() as db:
                db.execute(
                    "INSERT INTO users(username, email, password) VALUES(?,?,?)",
                    (username, email, generate_password_hash(password))
                )
            session["username"] = username
            return redirect("index.html")
        except sqlite3.IntegrityError:
            return "An account with that email already exists", 409

    # Passenger Login
    login_ident = email or username
    with connect() as db:
        user = db.execute(
            "SELECT username, password FROM users WHERE email=? OR username=?",
            (login_ident, login_ident)
        ).fetchone()

    if user and check_password_hash(user["password"], password):
        session["username"] = user["username"]
        return redirect("index.html")

    return "Invalid username or password", 401


@app.post("/db_connection.php")
@app.post("/api/conductor/login")
def conductor_login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    with connect() as db:
        user = db.execute("SELECT password FROM conductors WHERE username=?", (username,)).fetchone()
    if user and check_password_hash(user["password"], password):
        session["conductor"] = username
        return "success"
    return "Invalid username or password", 401


@app.post("/renew_pass.php")
@app.post("/process_renewal.php")
def renew_pass():
    pass_id = request.form.get("id", type=int)
    end_date = request.form.get("end_date", "").strip()
    if not pass_id or not end_date:
        return json_error("Pass ID and new end date are required")
    with connect() as db:
        cur = db.execute("UPDATE personal_details SET end_date=? WHERE id=?", (end_date, pass_id))
    return jsonify(status="success", message="Pass renewed successfully") if cur.rowcount else json_error("Pass not found", 404)


@app.get("/verify/<int:pass_id>")
def verify_pass_page(pass_id: int):
    with connect() as db:
        row = db.execute("SELECT * FROM personal_details WHERE id=?", (pass_id,)).fetchone()
    if not row:
        return render_template_string("""
        <!DOCTYPE html>
        <html><head><title>Pass Verification - Digi Bus Pass</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>body{font-family:'Times New Roman',serif;background:#f0f8ff;text-align:center;padding:50px;}</style>
        </head><body>
        <h2 style="color:red;">❌ INVALID BUS PASS</h2>
        <p>No bus pass record found for ID: {{ pass_id }}</p>
        <a href="/" style="display:inline-block;padding:10px 20px;background:darkblue;color:white;text-decoration:none;border-radius:5px;">Go to Portal</a>
        </body></html>
        """, pass_id=pass_id), 404

    data = public_pass(row)
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pass Verification - Digi Bus Pass</title>
        <style>
            body {
                font-family: 'Times New Roman', Times, serif;
                background: url('/pngtree-travel-bus-on-the-way-image_16005789.jpg') no-repeat center center fixed;
                background-size: cover;
                margin: 0; padding: 20px; min-height: 100vh;
                display: flex; justify-content: center; align-items: center;
            }
            .card {
                background: lightblue; border: 3px solid darkblue;
                border-radius: 12px; padding: 25px; max-width: 550px; width: 100%;
                box-shadow: 0 8px 25px rgba(0,0,139,0.4); text-align: center;
            }
            .badge-active {
                background: #28a745; color: white; padding: 6px 15px;
                border-radius: 20px; font-weight: bold; display: inline-block;
                margin-bottom: 15px; font-size: 15px;
            }
            .badge-pending {
                background: #e67e22; color: white; padding: 6px 15px;
                border-radius: 20px; font-weight: bold; display: inline-block;
                margin-bottom: 15px; font-size: 15px;
            }
            .photo {
                width: 120px; height: 140px; object-fit: cover;
                border: 2px solid darkblue; border-radius: 6px;
                background: white; margin: 10px auto;
            }
            table { width: 100%; margin: 15px 0; text-align: left; border-collapse: collapse; }
            td { padding: 6px 10px; font-size: 16px; color: darkblue; }
            td.lbl { font-weight: bold; width: 40%; }
            .btn {
                background: darkblue; color: white; padding: 10px 20px;
                border-radius: 5px; text-decoration: none; font-weight: bold;
                display: inline-block; margin-top: 15px;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <h2 style="color:darkblue; margin:0 0 10px;">OFFICIAL TRANSIT AUTHORITY</h2>
            <div class="{{ 'badge-active' if data.payment_status == 'paid' else 'badge-pending' }}">
                ● {{ 'VERIFIED ACTIVE PASS' if data.payment_status == 'paid' else 'CASH - PENDING COUNTER PAYMENT' }}
            </div>
            <br>
            <img class="photo" src="{{ data.photo or '/user-icon-for-web-site-login-head-sign-icon-design-free-vector.jpg' }}"
                 onerror="this.src='/user-icon-for-web-site-login-head-sign-icon-design-free-vector.jpg'">
            <table>
                <tr><td class="lbl">Pass Number:</td><td><strong>{{ data.pass_number }}</strong></td></tr>
                <tr><td class="lbl">Passenger Name:</td><td>{{ data.full_name }}</td></tr>
                <tr><td class="lbl">Category:</td><td>{{ data.pass_category | upper }}</td></tr>
                <tr><td class="lbl">Pass Type:</td><td>{{ data.pass_type | upper }}</td></tr>
                <tr><td class="lbl">Validity:</td><td>{{ data.start_date }} to {{ data.end_date }}</td></tr>
                <tr><td class="lbl">Route:</td><td>{{ data.route_number }} ({{ data.source_location }} to {{ data.destination_location }})</td></tr>
                <tr><td class="lbl">Mobile:</td><td>{{ data.mobile_number }}</td></tr>
                <tr><td class="lbl">Payment Ref:</td><td>{{ data.payment_reference or 'N/A' }}</td></tr>
            </table>
            <a class="btn" href="/">Return to Home</a>
        </div>
    </body>
    </html>
    """, data=data)


@app.get("/<path:filename>")
def static_files(filename):
    if filename.lower().endswith(".php"):
        return json_error("Endpoint not found", 404)
    return send_from_directory(ROOT, filename)


@app.get("/health")
def health():
    return jsonify(status="ok", database="sqlite", runtime="python")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
