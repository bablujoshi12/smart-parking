"""
Dashboard Routes Module
Handles dashboard and API endpoints
"""
from flask import Blueprint, render_template, jsonify
import mysql.connector

# Create blueprint for dashboard routes
dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route("/", methods=["GET"])
def index():
    """Show dashboard"""
    return render_template("dashboard.html")

@dashboard_bp.route("/api/parking-status", methods=["GET"])
def get_parking_status():
    """Real-time parking status API for dashboard"""
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartparking"
        )
        
        cursor = conn.cursor()
        
        # Count total cells
        cursor.execute("SELECT COUNT(*) FROM parking")
        total_cells = cursor.fetchone()[0]
        
        # Count available cells (status = 0)
        cursor.execute("SELECT COUNT(*) FROM parking WHERE Status = 0")
        available_cells = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "total_cells": total_cells,
            "available_cells": available_cells,
            "occupied_cells": total_cells - available_cells,
            "status": "success"
        }), 200
        
    except mysql.connector.Error as err:
        print(f"Database error in get_parking_status: {err}")
        return jsonify({"error": "Database error", "status": "error"}), 500
    except Exception as e:
        print(f"Error in get_parking_status: {e}")
        return jsonify({"error": "Internal server error", "status": "error"}), 500
