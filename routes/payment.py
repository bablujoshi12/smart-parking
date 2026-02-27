"""
Payment Routes Module
Handles Razorpay payment processing for exit functionality
"""
from flask import Blueprint, request, jsonify
import razorpay
import uuid
import mysql.connector
import os
from dotenv import load_dotenv
# Create blueprint for payment routes
payment_bp = Blueprint('payment', __name__)

# Razorpay config
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

# Initialize Razorpay client


razorpay_client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)

@payment_bp.route('/process_exit_payment', methods=['POST'])
def process_exit_payment():
    """Process payment for exit"""
    try:
        data = request.get_json()
        mobileNo = data.get('mobileNo')
        vehicleData = data.get('vehicleData')
        
        if not mobileNo or not vehicleData:
            return jsonify({"error": "Missing required data"}), 400
        
        # Create Razorpay order
        order_data = {
            'amount': int(vehicleData['amount']) * 100,  # Convert to paise
            'currency': 'INR',
            'receipt': f"parking_exit_{vehicleData['vehNo']}_{uuid.uuid4().hex[:8]}",
            'notes': {
                'vehicle_no': vehicleData['vehNo'],
                'cell_name': vehicleData['cellName'],
                'mobile_no': mobileNo
            }
        }
        
        order = razorpay_client.order.create(data=order_data)
        
        payment_data = {
            'key_id': RAZORPAY_KEY_ID,
            'amount': vehicleData['amount'],
            'order_id': order['id'],
            'currency': 'INR'
        }
        
        return jsonify({"paymentData": payment_data}), 200
        
    except Exception as e:
        print(f"Payment processing error: {e}")
        return jsonify({"error": "Payment processing failed"}), 500

@payment_bp.route('/confirm_exit_payment', methods=['POST'])
def confirm_exit_payment():
    """Confirm payment and update database"""
    try:
        data = request.get_json()
        mobileNo = data.get('mobileNo')
        vehicleData = data.get('vehicleData')
        paymentResponse = data.get('paymentResponse')
        
        if not mobileNo or not vehicleData or not paymentResponse:
            return jsonify({"error": "Missing payment data"}), 400
        
        # Verify payment with Razorpay
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': paymentResponse['razorpay_order_id'],
            'razorpay_payment_id': paymentResponse['razorpay_payment_id'],
            'razorpay_signature': paymentResponse['razorpay_signature']
        })
        
        # Update database - mark vehicle as exited
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="bablu@123456",
            database="smartparking"
        )
        cursor = conn.cursor()
        
        # Update reserve table with exit time
        cursor.execute("""
            UPDATE Reserve 
            SET OutTime = NOW() 
            WHERE MobNo = %s AND VehNo = %s AND OutTime IS NULL
        """, (int(mobileNo.replace('+', '').replace(' ', '')), vehicleData['vehNo']))
        
        # Update parking table - mark cell as available
        cursor.execute("""
            UPDATE parking 
            SET status = 0 
            WHERE Cell_id = (
                SELECT Cell_id FROM Reserve 
                WHERE MobNo = %s AND VehNo = %s AND OutTime IS NOT NULL
                ORDER BY Resid DESC LIMIT 1
            )
        """, (int(mobileNo.replace('+', '').replace(' ', '')), vehicleData['vehNo']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Send exit confirmation SMS
        from routes.twilio import send_sms_via_twilio
        sms_body = f"Exit confirmed for {vehicleData['vehNo']}. Payment of ₹{vehicleData['amount']} received. Thank you!"
        try:
            sid = send_sms_via_twilio(mobileNo, sms_body)
            print(f"Sent exit confirmation SMS SID {sid} to {mobileNo}")
        except Exception as e:
            print(f"Failed to send exit SMS: {e}")
        
        confirm_data = {
            'transaction_id': paymentResponse['razorpay_payment_id'],
            'amount': vehicleData['amount'],
            'status': 'success'
        }
        
        return jsonify(confirm_data), 200
        
    except razorpay.errors.SignatureVerificationError:
        return jsonify({"error": "Payment verification failed"}), 400
    except Exception as e:
        print(f"Payment confirmation error: {e}")
        return jsonify({"error": "Payment confirmation failed"}), 500
