"""
Exit Routes Module
Handles all exit-related functionality including OTP verification and vehicle lookup
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
from dotenv import load_dotenv
# Create blueprint for exit routes
exit_bp = Blueprint('exit', __name__)

# Twilio config

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_PHONE = os.getenv("TWILIO_FROM_PHONE")
# OTP config
OTP_LENGTH = 6
OTP_EXPIRY_SECONDS = 300

# Exit OTP store for separate exit functionality
exit_store = {}

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

@exit_bp.route("/exit", methods=["GET"])
def exit_page():
    """Exit page with complete exit flow"""
    return render_template("exit.html")

@exit_bp.route("/send_exit_otp", methods=["POST"])
def send_exit_otp():
    """Send OTP for exit"""
    try:
        data = request.get_json()
        mobile_no = data.get("mobileNo", "").strip()
        
        if not mobile_no:
            return jsonify({"error": "Mobile number is required"}), 400
        
        # Check if mobile number exists in database
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
            
        # First check if there's any active parking (OutTime IS NULL)
        cursor.execute("""
            SELECT r.Resid, r.Cell_id, r.VehNo, r.InTime, r.MobNo, p.Cell_Name
            FROM reserve r
            INNER JOIN parking p ON r.Cell_id = p.Cell_id
            WHERE r.MobNo = %s AND r.OutTime IS NULL
        """, (mobile_int,))
        
        active_vehicle = cursor.fetchone()
        
        # If no active parking, check if there's any recent exit (within last 5 minutes)
        if not active_vehicle:
            cursor.execute("""
                SELECT r.Resid, r.Cell_id, r.VehNo, r.InTime, r.OutTime, r.MobNo, p.Cell_Name
                FROM reserve r
                INNER JOIN parking p ON r.Cell_id = p.Cell_id
                WHERE r.MobNo = %s AND r.OutTime IS NOT NULL
                ORDER BY r.OutTime DESC LIMIT 1
            """, (mobile_int,))
            
            recent_exit = cursor.fetchone()
            
            if recent_exit:
                return jsonify({
                    "error": f"This mobile number has already exited parking for vehicle {recent_exit['VehNo']} from cell {recent_exit['Cell_Name']}. Please wait before making a new reservation or contact support if this is an error."
                }), 400
            else:
                return jsonify({"error": "No active parking found for this mobile number"}), 404
        
        vehicle = active_vehicle
        cursor.close()
        conn.close()
        
        # Generate OTP
        otp = generate_otp(OTP_LENGTH)
        salt = hashlib.sha256(os.urandom(64)).hexdigest()
        secret_key = os.getenv("APP_SECRET_KEY") or "default_secret"
        otp_hash = make_otp_hash(otp, salt, secret_key)
        expires_at = time.time() + OTP_EXPIRY_SECONDS
        
        # Store OTP
        exit_store[mobile_no] = {
            'otp_hash': otp_hash,
            'salt': salt,
            'expires_at': expires_at,
            'vehicle': vehicle
        }
        
        # Send SMS via Twilio
        sms_body = f"Your Exit OTP is: {otp}. Valid for {OTP_EXPIRY_SECONDS//60} minutes."
        try:
            sid = send_sms_via_twilio(mobile_no, sms_body)
            print(f"Sent exit OTP SID {sid} to {mobile_no}")
        except Exception as e:
            print(f"Failed to send exit SMS: {e}")
            return jsonify({"error": "Failed to send OTP. Please check your mobile number."}), 500
        
        return jsonify({"message": "OTP sent successfully"}), 200
        
    except mysql.connector.Error as err:
        print(f"Database error in send_exit_otp: {err}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        print(f"Error in send_exit_otp: {e}")
        return jsonify({"error": "Internal server error"}), 500

@exit_bp.route("/verify_exit_otp", methods=["POST"])
def verify_exit_otp():
    """Verify OTP for exit and return vehicle details"""
    try:
        data = request.get_json()
        mobile_no = data.get("mobileNo", "").strip()
        otp_code = data.get("otp", "").strip()
        
        if not mobile_no or not otp_code:
            return jsonify({"error": "Mobile number and OTP are required"}), 400
        
        # Check OTP
        record = exit_store.get(mobile_no)
        if not record:
            return jsonify({"error": "No OTP found for this mobile number"}), 404
        
        # Check expiry
        now = time.time()
        if now > record.get('expires_at', 0):
            exit_store.pop(mobile_no, None)
            return jsonify({"error": "OTP expired"}), 400
        
        # Verify OTP
        secret_key = os.getenv("APP_SECRET_KEY") or "default_secret"
        provided_hash = make_otp_hash(otp_code, record['salt'], secret_key)
        if not hmac.compare_digest(provided_hash, record['otp_hash']):
            return jsonify({"error": "Invalid OTP"}), 400
        
        # Calculate parking duration and amount (simplified version)
        vehicle = record['vehicle']
        entry_time = vehicle['InTime']
        current_time = datetime.now()
        
        # Calculate duration in hours
        duration_hours = (current_time - entry_time).total_seconds() / 3600
        duration_hours = max(1, round(duration_hours))  # Minimum 1 hour
        
        # Calculate charges based on pricing structure
        if duration_hours <= 1:
            total_charge = 30
        elif duration_hours <= 2:
            total_charge = 30 + (duration_hours - 1) * 25
        elif duration_hours <= 3:
            total_charge = 55 + (duration_hours - 2) * 20
        elif duration_hours <= 4:
            total_charge = 75 + (duration_hours - 3) * 15
        else:
            total_charge = 90 + (duration_hours - 4) * 10
        
        # Format duration text
        hours_int = int(duration_hours)
        minutes_int = int((duration_hours - hours_int) * 60)
        
        if hours_int == 0:
            duration_text = f"{minutes_int} Min"
        elif minutes_int == 0:
            duration_text = f"{hours_int} Hr{'s' if hours_int > 1 else ''}"
        else:
            duration_text = f"{hours_int} Hr{'s' if hours_int > 1 else ''} {minutes_int} Min"
        
        vehicle_info = {
            'vehNo': vehicle['VehNo'],
            'cellName': vehicle['Cell_Name'],
            'inTime': entry_time.strftime('%Y-%m-%d %H:%M:%S'),
            'duration': duration_text,
            'amount': total_charge
        }
        
        return jsonify({"vehicle": vehicle_info}), 200
        
    except Exception as e:
        print(f"Error in verify_exit_otp: {e}")
        return jsonify({"error": "Internal server error"}), 500

@exit_bp.route('/get_exit', methods=["GET", "POST"])
def get_exit():
    """Get parking exit status"""
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartparking"
        )
        
        cursor = conn.cursor(dictionary=True)
        cursor.callproc('GetParkingExitStatus')
               
        result = None
        for result_set in cursor.stored_results():
            result = result_set.fetchone()
            break
        
        cursor.close()
        conn.close()
        
        if result:
            return jsonify(result), 200
        else:
            print("Error: result is None:")
            return jsonify({"error": f"No data found"}), 404
    except mysql.connector.Error as err:
        print(f"SQL Error: {err}")
        return jsonify({"error": "Database error occurred", "details": str(err)}), 500
    except Exception as e:
        print(f"Unexpected error: {e}")
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@exit_bp.route('/update_exit_status', methods=['POST'])
def update_exit_status():
    """Update exit status from ESP32"""
    try:        
        # Parse JSON data from ESP32
        data = request.get_json()
        res_id = int(data.get("res_id"))
        
        print("Update Exit Status: " + str(res_id))
        
        if res_id is None:
            return jsonify({"error": "Missing parameters"}), 400
        
        # Connect to MySQL
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartparking"
        )
        
        cursor = conn.cursor()
        cursor.callproc("UpdateParkingExitStatus", [res_id])
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({"message": "Entry status updated successfully"}), 200
        
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return jsonify({"error": str(err)}), 500
    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500