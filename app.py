"""
Main Flask Application
Smart Parking System with modular route structure
"""
import os
from dotenv import load_dotenv
from flask import Flask

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)
app.secret_key = os.getenv("APP_SECRET_KEY") or os.urandom(24)

# Import and register blueprints
from routes.dashboard import dashboard_bp
from routes.entry import entry_bp
from routes.exit import exit_bp
from routes.payment import payment_bp
from routes.twilio import twilio_bp

# Register blueprints
app.register_blueprint(dashboard_bp)
app.register_blueprint(entry_bp)
app.register_blueprint(exit_bp)
app.register_blueprint(payment_bp)
app.register_blueprint(twilio_bp)

# Legacy routes (keeping for backward compatibility)
@app.route("/verify", methods=["GET", "POST"])
def verify():
    """Legacy verify route - redirect to entry page"""
    from flask import redirect, url_for
    return redirect(url_for('entry.entry_page'))

@app.route("/resend", methods=["POST"])
def resend():
    """Legacy resend route - redirect to entry page"""
    from flask import redirect, url_for
    return redirect(url_for('entry.entry_page'))

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
