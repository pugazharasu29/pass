# Digi Bus Pass

Digi Bus Pass keeps the existing HTML/CSS frontend and runs its application logic in Flask. SQLite replaces the XAMPP MySQL database. The main application flow is the form at `digibusform.html`, the generated pass at `buspassgenerator002.html`, and conductor verification through the existing scanner pages.

## Run locally

1. Install Python 3.10 or newer.
2. Create and activate a virtual environment, then run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set a long random `SECRET_KEY`.
4. Set Razorpay test credentials in the environment to exercise online checkout. Without credentials, online checkout fails clearly and no pass payment is marked successful. Never put live credentials in source control.
5. Run `python app.py`, then open `http://127.0.0.1:5000`.

The SQLite database is created in `instance/digibuspass.sqlite3`. Uploaded passenger photos and private identity documents are kept under `instance/`; identity documents are not served by the web application. Keep backups of the instance directory when running outside a disposable demo environment.

## Payments

Online card, UPI and net banking payments use Razorpay Checkout. The server creates the order and verifies Razorpay's HMAC signature before allowing an application to be recorded as paid. The demo cannot accept real money until the owner configures live Razorpay credentials and a verified merchant account. Cash remains a pending payment and is not equivalent to a paid online pass.

## Pass format

The existing pass card design is preserved. It shows the passenger photo and details, a readable pass number (`DBP-000001` format), validity dates, route, and a QR code containing the pass ID and verification details. A conductor scanner can look up the pass ID through the Flask endpoint.

## Deploy

`render.yaml` defines a Render web service. Push the repository to GitHub, then choose **New > Blueprint** in Render and select this repository. Set Razorpay credentials in the Render service environment for online payment. The included free web service stores SQLite and uploads on an ephemeral filesystem, so data does not survive replacement/redeployment; use persistent storage or a managed PostgreSQL database before using it for real passengers. GitHub Pages only serves static files and cannot run this Python backend.

## Data and account setup

- Do not commit `.env`, SQLite data, uploads, identity files, or credential lists.
- Set `SECRET_KEY` in production and configure `CONDUCTOR_USERNAME` plus `CONDUCTOR_PASSWORD` in the environment. The app stores the conductor password as a hash.
- Existing MySQL records are not copied automatically; export and migrate them separately if needed.
