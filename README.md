# 🚌 Digi Bus Pass - Digital Bus Pass Management System

Digi Bus Pass is a Python Flask and SQLite web application that digitizes transit ticketing. Commuters apply online, pay securely via Razorpay or dynamic UPI QR codes, and receive an official digital bus pass with photo and QR code for PDF download or printing. It also provides conductors with a live camera QR scanner for instant pass verification.

---

## 🌟 Highlights & Key Improvements

1. **🐍 Python (Flask) Backend**: Complete migration from legacy PHP to Python Flask with structured routing, modular error handling, and session management.
2. **💾 SQLite Database Engine**: Replaced XAMPP MySQL with self-contained, zero-configuration SQLite persistence (`instance/digibuspass.sqlite3`).
3. **💳 Original Payment Integration**:
   - **Razorpay Checkout**: Full support for UPI, Google Pay, PhonePe, Paytm, Debit/Credit Cards, and Net Banking with HMAC SHA-256 signature verification.
   - **Dynamic UPI QR Code**: Real-time QR code generation with amount and UPI merchant parameters.
   - **Integrated Instant Gateway Simulator**: Test online checkout and instant verification even without live API keys.
   - **Cash Payment Option**: Generates verified depot counter registration references.
4. **🎫 Perfect Official Pass Format**:
   - State Road Transport Corporation official transit pass layout.
   - Security features: Holographic watermarked background (`DIGIBUSPASS`), tamper-proof status badges, formatted serial numbers (`DBP-000001`).
   - High-resolution dynamic QR Code containing pass details and verification URL (`/verify/<id>`).
   - One-click **PDF Download** and **Direct Print** (`@media print` optimized for ID card & standard paper).
5. **🔍 Conductor QR Scanner**: Live camera QR scanner and manual Pass ID search with instant validity verification.
6. **🎨 Preserved Frontend Design**: 100% visual fidelity to the original design, background wallpapers, colors, and typography.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10 or higher installed.

### 2. Setup & Installation
Clone the repository:
```bash
git clone https://github.com/pugazharasu29/pass.git
cd pass
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration (Optional)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Configure your environment variables:
- `SECRET_KEY`: Random session secret.
- `RAZORPAY_KEY_ID`: Your Razorpay Key ID (optional, simulation mode is active if empty).
- `RAZORPAY_KEY_SECRET`: Your Razorpay Key Secret.
- `CONDUCTOR_USERNAME`: Conductor login username (default: `conductor`).
- `CONDUCTOR_PASSWORD`: Conductor login password (default: `conductor123`).

### 4. Run Locally
```bash
python app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 📂 Project Structure

```
├── app.py                      # Main Flask application and RESTful backend
├── index.html                  # Portal homepage & active pass viewer
├── digibusform.html            # Pass application & interactive payment form
├── buspassgenerator002.html    # Official digital pass card & PDF generator
├── conductor.html              # Conductor portal login
├── qr_scanner.html             # Camera QR code scanner for ticket conductors
├── renew_pass.html             # Online pass renewal portal
├── passanger.html              # Passenger account login & registration
├── about.html                  # About Us page
├── requirements.txt            # Python dependencies
├── render.yaml                 # Production deployment blueprint
├── instance/
│   ├── digibuspass.sqlite3     # SQLite database
│   ├── uploads/                # Passenger photos
│   └── private_uploads/        # Identity proof documents
└── IMAGES/                     # Transit icons and logos
```

---

## 🛡️ Default Conductor Credentials

| Role | Username | Password |
| :--- | :--- | :--- |
| **Bus Conductor** | `conductor` | `conductor123` |

---

## 🚢 Deployment

### Deploy to Render
This repository includes a `render.yaml` blueprint. To deploy:
1. Fork or push this repository to your GitHub account.
2. In Render, select **New > Blueprint**.
3. Connect your repository.
4. Set your production environment variables (`SECRET_KEY`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`).

---

## 📜 License
Developed as part of the Digi Bus Pass Mini Project.
