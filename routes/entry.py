"""
Entry Routes Module
Handles all entry-related functionality including OTP sending and verification
"""

from flask import Blueprint, render_template, request, jsonify, session
import os
import hmac
import hashlib
import random
import time
from twilio.rest import Client
import mysql.connector

entry_bp = Blueprint('entry', __name__)

# Twilio Config
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_PHONE = os.getenv("TWILIO_FROM_PHONE")

OTP_LENGTH = 6
OTP_EXPIRY_SECONDS = 300

store = {}

# ---------------- OTP Utilities ----------------

def generate_otp(length=6):
    return str(random.randint(0, 999999)).zfill(length)

def make_otp_hash(otp: str, salt: str, secret_key: str):
    key = (str(secret_key) + salt).encode()
    return hmac.new(key, otp.encode(), hashlib.sha256).hexdigest()

def send_sms_via_twilio(to_phone: str, body: str):
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        body=body,
        from_=TWILIO_FROM_PHONE,
        to=to_phone
    )
    return message.sid

# ---------------- Entry Page ----------------

@entry_bp.route("/entry", methods=["GET"])
def entry_page():
    return render_template("entry.html")

# ---------------- Send Entry OTP ----------------

@entry_bp.route("/send_entry_otp", methods=["POST"])
def send_entry_otp():
    try:
        data = request.get_json()
        mobile_no = data.get("mobileNo", "").strip()

        if not mobile_no:
            return jsonify({"error": "Mobile number required"}), 400

        mobile_int = int(mobile_no.replace('+', '').replace(' ', ''))

        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartparking"
        )
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT r.Resid
            FROM reserve r
            WHERE r.MobNo = %s AND r.OutTime IS NULL
        """, (mobile_int,))

        if cursor.fetchone():
            return jsonify({"error": "Mobile already has active parking"}), 400

        cursor.close()
        conn.close()

        otp = generate_otp(OTP_LENGTH)
        salt = hashlib.sha256(os.urandom(64)).hexdigest()
        secret_key = os.getenv("APP_SECRET_KEY") or "default_secret"
        otp_hash = make_otp_hash(otp, salt, secret_key)

        store[mobile_no] = {
            "otp_hash": otp_hash,
            "salt": salt,
            "expires_at": time.time() + OTP_EXPIRY_SECONDS
        }

        send_sms_via_twilio(mobile_no, f"Your Entry OTP is: {otp}")

        return jsonify({"message": "OTP sent"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- Verify OTP ----------------

@entry_bp.route("/verify_entry_otp", methods=["POST"])
def verify_entry_otp():
    try:
        data = request.get_json()
        mobile_no = data.get("mobileNo")
        otp_code = data.get("otp")

        record = store.get(mobile_no)

        if not record:
            return jsonify({"error": "No OTP found"}), 400

        if time.time() > record["expires_at"]:
            return jsonify({"error": "OTP expired"}), 400

        secret_key = os.getenv("APP_SECRET_KEY") or "default_secret"
        provided_hash = make_otp_hash(otp_code, record["salt"], secret_key)

        if not hmac.compare_digest(provided_hash, record["otp_hash"]):
            return jsonify({"error": "Invalid OTP"}), 400

        session["otp_phone"] = mobile_no
        return jsonify({"message": "OTP verified"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- Reserve Parking ----------------

@entry_bp.route('/get_data', methods=["POST"])
def get_data():
    try:
        data = request.get_json()
        vehNo = data.get("vehNo")
        phone = session.get("otp_phone")

        if not phone:
            return jsonify({"error": "OTP not verified"}), 400

        mobNo = int(phone.replace('+', '').replace(' ', ''))

        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartparking"
        )

        cursor = conn.cursor(dictionary=True)
        cursor.callproc('ReserveCellToVehicle', [vehNo, mobNo])

        result = None
        for rs in cursor.stored_results():
            result = rs.fetchone()
            break

        conn.commit()
        cursor.close()
        conn.close()

        if result:
            return jsonify({
                "cellID": result.get("cellID"),
                "cellName": result.get("cellName"),
                "vehNo": result.get("vehNo"),
                "vacantCells": result.get("vacantCells")
            }), 200

        return jsonify({"error": "Reservation failed"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- ESP32 Route: Get Pending Entry ----------------

@entry_bp.route('/get_pending_entry', methods=['GET'])
def get_pending_entry():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartparking"
        )

        cursor = conn.cursor(dictionary=True)
        cursor.callproc('GetPendingEntry')

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

# ---------------- ESP32 Route: Update Entry Status ----------------

@entry_bp.route('/update_entry_status', methods=['POST'])
def update_entry_status():
    try:
        data = request.get_json()

        print("ESP32 Data:", data)

        res_id = int(data.get("res_id"))
        gate_status = int(data.get("gate_status"))

        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartparking"
        )

        cursor = conn.cursor()

        cursor.execute("""
        UPDATE reserve
        SET enStat = %s
        WHERE Resid = %s
        """, (gate_status, res_id))

        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "updated"}), 200

    except Exception as e:
        print("Update Entry Error:", e)
        return jsonify({"error": str(e)}), 500