"""
Twilio Routes Module
Handles SMS functionality using Twilio
"""
import os
from flask import Blueprint
from twilio.rest import Client
from dotenv import load_dotenv
# Create blueprint for Twilio routes
twilio_bp = Blueprint('twilio', __name__)

# Twilio config


TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_PHONE = os.getenv("TWILIO_FROM_PHONE")

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
