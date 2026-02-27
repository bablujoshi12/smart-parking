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
from dotenv import load_dotenv

# Create blueprint for entry routes
entry_bp = Blueprint('entry', __name__)

# Twilio config

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_PHONE = os.getenv("TWILIO_FROM_PHONE")

# OTP config
OTP_LENGTH = 6
OTP_EXPIRY_SECONDS = 300

# Basic in-memory store for demo
store = {}

def generate_otp(length=6):
    """Generate numeric OTP as string, zero-padded."""
    range_start = 10**(length-1)
    range_end = (10**length) - 1
    n = random.randint(0, range_end)
    return str(n).zfill(length)

def make_otp_hash(otp: str, salt: str, secret_key: str):
    """Return HMAC-SHA256 of otp using app secret + salt."""
    key = (str(secret_key) + salt).encode()
    return hmac.new(key, otp.encode(), hashlib.sha256).hexdigest()

def send_sms_via_twilio(to_phone: str, body: str):
    """Send SMS via Twilio"""
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_PHONE):
        raise RuntimeError("Twilio credentials not configured.")
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        body=body,
        from_=TWILIO_FROM_PHONE,
        to=to_phone
    )
    return message.sid

@entry_bp.route("/entry", methods=["GET"])
def entry_page():
    """Entry page with simplified flow"""
    return render_template("entry.html")

@entry_bp.route("/send_entry_otp", methods=["POST"])
def send_entry_otp():
    """Send OTP for entry"""
    try:
        data = request.get_json()
        mobile_no = data.get("mobileNo", "").strip()
        
        if not mobile_no:
            return jsonify({"error": "Mobile number is required"}), 400
        
        # Check if mobile number already has active parking
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartparking"
        )
        
        cursor = conn.cursor(dictionary=True)
        # Convert mobile number to integer for database comparison
        try:
            mobile_int = int(mobile_no.replace('+', '').replace(' ', ''))
        except ValueError:
            return jsonify({"error": "Invalid mobile number format"}), 400
            
        # Check if mobile number already has active parking (OutTime IS NULL)
        cursor.execute("""
            SELECT r.Resid, r.Cell_id, r.VehNo, r.InTime, r.MobNo, p.Cell_Name
            FROM reserve r
            INNER JOIN parking p ON r.Cell_id = p.Cell_id
            WHERE r.MobNo = %s AND r.OutTime IS NULL
        """, (mobile_int,))
        
        existing_parking = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if existing_parking:
            return jsonify({
                "error": f"This mobile number already has active parking for vehicle {existing_parking['VehNo']} in cell {existing_parking['Cell_Name']}. Please exit first before making a new reservation."
            }), 400
        
        # Generate OTP
        otp = generate_otp(OTP_LENGTH)
        salt = hashlib.sha256(os.urandom(64)).hexdigest()
        secret_key = os.getenv("APP_SECRET_KEY") or "default_secret"
        otp_hash = make_otp_hash(otp, salt, secret_key)
        expires_at = time.time() + OTP_EXPIRY_SECONDS
        
        # Store OTP
        store.setdefault(mobile_no, {}).update({
            'otp_hash': otp_hash,
            'salt': salt,
            'expires_at': expires_at,
            'verify_attempts': 0,
        })
        
        # Send SMS via Twilio
        sms_body = f"Your Entry OTP is: {otp}. Valid for {OTP_EXPIRY_SECONDS//60} minutes."
        try:
            sid = send_sms_via_twilio(mobile_no, sms_body)
            print(f"Sent entry OTP SID {sid} to {mobile_no}")
        except Exception as e:
            print(f"Failed to send entry SMS: {e}")
            return jsonify({"error": "Failed to send OTP. Please check your mobile number."}), 500
        
        return jsonify({"message": "OTP sent successfully"}), 200
        
    except mysql.connector.Error as err:
        print(f"Database error in send_entry_otp: {err}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        print(f"Error in send_entry_otp: {e}")
        return jsonify({"error": "Internal server error"}), 500

@entry_bp.route("/verify_entry_otp", methods=["POST"])
def verify_entry_otp():
    """Verify OTP for entry"""
    try:
        data = request.get_json()
        mobile_no = data.get("mobileNo", "").strip()
        otp_code = data.get("otp", "").strip()
        
        if not mobile_no or not otp_code:
            return jsonify({"error": "Mobile number and OTP are required"}), 400
        
        # Check OTP
        record = store.get(mobile_no)
        if not record:
            return jsonify({"error": "No OTP found for this mobile number"}), 404
        
        # Check expiry
        now = time.time()
        if now > record.get('expires_at', 0):
            store.pop(mobile_no, None)
            return jsonify({"error": "OTP expired"}), 400
        
        # Verify OTP
        secret_key = os.getenv("APP_SECRET_KEY") or "default_secret"
        provided_hash = make_otp_hash(otp_code, record['salt'], secret_key)
        if not hmac.compare_digest(provided_hash, record['otp_hash']):
            return jsonify({"error": "Invalid OTP"}), 400
        
        # Store verified mobile in session for later use
        session['otp_phone'] = mobile_no
        
        return jsonify({"message": "OTP verified successfully"}), 200
        
    except Exception as e:
        print(f"Error in verify_entry_otp: {e}")
        return jsonify({"error": "Internal server error"}), 500

@entry_bp.route('/get_data', methods=["GET", "POST"])
def get_data():
    """Reserve parking cell for vehicle"""
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartparking"
        )
        
        data = request.get_json()
        vehNo = data.get("vehNo")
        phone_from_session = session.get("otp_phone")
        
        # Convert phone number to integer format for database compatibility
        try:
            mobNo = int(phone_from_session.replace('+', '').replace(' ', ''))
        except (ValueError, AttributeError):
            return jsonify({"error": "Invalid phone number in session"}), 400

        cursor = conn.cursor(dictionary=True)
        cursor.callproc('ReserveCellToVehicle', [vehNo, mobNo])
        
        result = None
        for result_set in cursor.stored_results():
            result = result_set.fetchone()
            break

        cursor.close()
        conn.close()

        if result:
            sms_body = f"Parking Cell for your Vehicle {vehNo} is: {result['cellName']}"
            try:
                phone = session.get("otp_phone")
                sid = send_sms_via_twilio(phone, sms_body)
                print(f"Sent parking confirmation SMS SID {sid} to {phone}")
            except Exception as e:
                print(f"Failed to send SMS: {e}")
                print(f"Development Mode - SMS would be: {sms_body}")
            
            response_data = {
                'cellID': result.get('cellID'),
                'cellName': result.get('cellName'),
                'vehNo': result.get('vehNo'),
                'vacantCells': result.get('vacantCells', 0)
            }
            return jsonify(response_data), 200
        else:
            return jsonify({"error": f"No data found for vehicle {vehNo}"}), 404
    except mysql.connector.Error as err:
        print(f"SQL Error: {err}")
        return jsonify({"error": "Database error occurred", "details": str(err)}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@entry_bp.route('/reserve_parking', methods=["GET", "POST"])
def reserve_parking():
    """Reserve parking cell for vehicle (alias for get_data)"""
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartparking"
        )
        
        data = request.get_json()
        vehNo = data.get("vehNo")
        phone_from_session = session.get("otp_phone")
        
        # Convert phone number to integer format for database compatibility
        try:
            mobNo = int(phone_from_session.replace('+', '').replace(' ', ''))
        except (ValueError, AttributeError):
            return jsonify({"error": "Invalid phone number in session"}), 400
        
        cursor = conn.cursor(dictionary=True)
        cursor.callproc('ReserveCellToVehicle', [vehNo, mobNo])
        
        result = None
        for result_set in cursor.stored_results():
            result = result_set.fetchone()
            break
        
        cursor.close()
        conn.close()
        
        if result:
            sms_body = f"Parking Cell for your Vehicle {vehNo} is: {result['cellName']}"
            try:
                phone = session.get("otp_phone")
                sid = send_sms_via_twilio(phone, sms_body)
                print(f"Sent parking confirmation SMS SID {sid} to {phone}")
            except Exception as e:
                print(f"Failed to send SMS: {e}")
            
            return jsonify(result), 200
        else:
            return jsonify({"error": f"No data found for vehicle {vehNo}"}), 404
    except mysql.connector.Error as err:
        print(f"SQL Error: {err}")
        return jsonify({"error": "Database error occurred", "details": str(err)}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@entry_bp.route('/get_entry', methods=["GET", "POST"])
def get_entry():
    """Get parking allotment status"""
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartparking"
        )
        
        cursor = conn.cursor(dictionary=True)
        cursor.callproc('GetParkingAllotmentStatus')
        
        result = None
        for result_set in cursor.stored_results():
            result = result_set.fetchone()
            break
        
        cursor.close()
        conn.close()
        
        if result:
            return jsonify(result), 200
        else:
            return jsonify({"error": f"No data found"}), 404
    except mysql.connector.Error as err:
        print(f"SQL Error: {err}")
        return jsonify({"error": "Database error occurred", "details": str(err)}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@entry_bp.route('/update_entry_status', methods=['POST'])
def update_entry_status():
    """Update entry status from ESP32"""
    try:        
        # Parse JSON data from ESP32
        data = request.get_json()
        res_id = int(data.get("res_id"))
        gate_status = int(data.get("gate_status"))
        
        print(res_id)
        print(gate_status)
        
        if res_id is None or gate_status is None:
            return jsonify({"error": "Missing parameters"}), 400
        
        # Connect to MySQL
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartparking"
        )
        cursor = conn.cursor()
        
        # Call stored procedure UpdateEntryStatus(cell_id, gate_status)
        cursor.callproc("UpdateEntryStatus", [res_id, gate_status])
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({"message": "Updated"}), 200
        
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return jsonify({"error": str(err)}), 500
    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500