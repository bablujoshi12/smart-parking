"""
Payment Routes Module
Handles Razorpay payment processing for exit functionality
"""

from flask import Blueprint, request, jsonify
import razorpay
import uuid
import mysql.connector
import os

payment_bp = Blueprint('payment', __name__)

# Razorpay config
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

razorpay_client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)


# ---------------------------------------------------
# STEP 1: CREATE ORDER
# ---------------------------------------------------

@payment_bp.route('/process_exit_payment', methods=['POST'])
def process_exit_payment():
    try:
        data = request.get_json()
        mobileNo = data.get('mobileNo')
        vehicleData = data.get('vehicleData')

        if not mobileNo or not vehicleData:
            return jsonify({"error": "Missing required data"}), 400

        order_data = {
            'amount': int(vehicleData['amount']) * 100,
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
        print("Payment processing error:", e)
        return jsonify({"error": "Payment processing failed"}), 500


# ---------------------------------------------------
# STEP 2: CONFIRM PAYMENT
# ---------------------------------------------------

@payment_bp.route('/confirm_exit_payment', methods=['POST'])
def confirm_exit_payment():
    try:
        data = request.get_json()
        mobileNo = data.get('mobileNo')
        vehicleData = data.get('vehicleData')
        paymentResponse = data.get('paymentResponse')

        if not mobileNo or not vehicleData or not paymentResponse:
            return jsonify({"error": "Missing payment data"}), 400

        # Verify Razorpay signature
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': paymentResponse['razorpay_order_id'],
            'razorpay_payment_id': paymentResponse['razorpay_payment_id'],
            'razorpay_signature': paymentResponse['razorpay_signature']
        })

        # -------------------------------
        # IMPORTANT CHANGE HERE
        # Only mark exStat = 2
        # -------------------------------

        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartparking"
        )

        cursor = conn.cursor()

        cursor.execute("""
            UPDATE reserve
            SET exStat = 2
            WHERE MobNo = %s
              AND VehNo = %s
              AND exStat = 1
        """, (
            int(mobileNo.replace('+', '').replace(' ', '')),
            vehicleData['vehNo']
        ))

        conn.commit()
        cursor.close()
        conn.close()

        # Optional SMS
        try:
            from routes.twilio import send_sms_via_twilio
            sms_body = f"Payment received for {vehicleData['vehNo']}. Exit gate will open shortly."
            send_sms_via_twilio(mobileNo, sms_body)
        except Exception as e:
            print("SMS error:", e)

        return jsonify({
            "transaction_id": paymentResponse['razorpay_payment_id'],
            "amount": vehicleData['amount'],
            "status": "success"
        }), 200

    except razorpay.errors.SignatureVerificationError:
        return jsonify({"error": "Payment verification failed"}), 400

    except Exception as e:
        print("Payment confirmation error:", e)
        return jsonify({"error": "Payment confirmation failed"}), 500