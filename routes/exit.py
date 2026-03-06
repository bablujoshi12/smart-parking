"""
Exit Routes Module
Handles exit OTP, vehicle lookup, ESP32 integration
"""

from flask import Blueprint, render_template, request, jsonify
import os
import hmac
import hashlib
import random
import time
from datetime import datetime
from twilio.rest import Client
import mysql.connector

exit_bp = Blueprint('exit', __name__)

# ========================
# CONFIG
# ========================

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_PHONE = os.getenv("TWILIO_FROM_PHONE")

OTP_LENGTH = 6
OTP_EXPIRY_SECONDS = 300

exit_store = {}

# ========================
# HELPER FUNCTIONS
# ========================

def generate_otp(length=6):
    return str(random.randint(0, (10**length) - 1)).zfill(length)

def make_otp_hash(otp, salt, secret_key):
    key = (str(secret_key) + salt).encode()
    return hmac.new(key, otp.encode(), hashlib.sha256).hexdigest()

def send_sms_via_twilio(to_phone, body):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        body=body,
        from_=TWILIO_FROM_PHONE,
        to=to_phone
    )
    return message.sid

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="smartparking"
    )

# ========================
# ROUTES
# ========================

@exit_bp.route("/exit")
def exit_page():
    return render_template("exit.html")


# =========================================
# 1️⃣ SEND EXIT OTP
# =========================================
@exit_bp.route("/send_exit_otp", methods=["POST"])
def send_exit_otp():
    try:
        data = request.get_json()
        mobile_no = data.get("mobileNo", "").strip()

        if not mobile_no:
            return jsonify({"error": "Mobile required"}), 400

        mobile_int = int(mobile_no.replace('+', '').replace(' ', ''))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT r.Resid, r.Cell_id, r.VehNo, r.InTime, p.Cell_Name
            FROM reserve r
            INNER JOIN parking p ON r.Cell_id = p.Cell_id
            WHERE r.MobNo = %s AND r.OutTime IS NULL
        """, (mobile_int,))

        vehicle = cursor.fetchone()
        cursor.close()
        conn.close()

        if not vehicle:
            return jsonify({"error": "No active parking"}), 404

        otp = generate_otp(OTP_LENGTH)
        salt = hashlib.sha256(os.urandom(64)).hexdigest()
        secret_key = os.getenv("APP_SECRET_KEY") or "default_secret"
        otp_hash = make_otp_hash(otp, salt, secret_key)

        exit_store[mobile_no] = {
            "otp_hash": otp_hash,
            "salt": salt,
            "expires": time.time() + OTP_EXPIRY_SECONDS,
            "vehicle": vehicle
        }

        send_sms_via_twilio(mobile_no, f"Your Exit OTP: {otp}")

        return jsonify({"message": "OTP sent"}), 200

    except Exception as e:
        print(e)
        return jsonify({"error": "Internal error"}), 500


# =========================================
# 2️⃣ VERIFY EXIT OTP
# =========================================
@exit_bp.route("/verify_exit_otp", methods=["POST"])
def verify_exit_otp():
    try:
        data = request.get_json()
        mobile_no = data.get("mobileNo")
        otp = data.get("otp")

        record = exit_store.get(mobile_no)

        if not record:
            return jsonify({"error": "No OTP found"}), 400

        if time.time() > record["expires"]:
            return jsonify({"error": "OTP expired"}), 400

        secret_key = os.getenv("APP_SECRET_KEY") or "default_secret"
        provided_hash = make_otp_hash(otp, record["salt"], secret_key)

        if not hmac.compare_digest(provided_hash, record["otp_hash"]):
            return jsonify({"error": "Invalid OTP"}), 400

        vehicle = record["vehicle"]

        duration_hours = max(
            1,
            round((datetime.now() - vehicle["InTime"]).total_seconds() / 3600)
        )

        amount = 30 + max(0, duration_hours - 1) * 20

        # 🔹 FIXED RESPONSE STRUCTURE
        return jsonify({
            "vehicle": {
                "vehNo": vehicle["VehNo"],
                "cellName": vehicle["Cell_Name"],
                "inTime": vehicle["InTime"].isoformat(),
                "duration": f"{duration_hours} hour(s)",
                "amount": amount
            }
        }), 200

    except Exception as e:
        print("OTP Verify Error:", e)
        return jsonify({"error": "Internal error"}), 500


# =========================================
# 3️⃣ ESP32 CHECK PENDING EXIT
# =========================================
@exit_bp.route("/get_pending_exit", methods=["GET"])
def get_pending_exit():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.callproc("GetPendingExit")

        result = None
        for rs in cursor.stored_results():
            result = rs.fetchone()
            break

        cursor.close()
        conn.close()

        if result:
            return jsonify(result), 200
        else:
            return jsonify({"res_id": 0}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================================
# 4️⃣ ESP32 UPDATE EXIT STATUS
# =========================================
@exit_bp.route("/update_exit_status", methods=["POST"])
def update_exit_status():
    try:
        data = request.get_json()
        res_id = int(data.get("res_id"))

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.callproc("UpdateParkingExitStatus", [res_id])

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Updated"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500