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


@dashboard_bp.route("/latest_slot_assignment", methods=["GET"])
def latest_slot_assignment():
    """Latest enStat=1 reservation for slot guidance"""
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartparking"
        )
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT r.Resid, r.VehNo, r.Cell_id, p.Cell_Name
            FROM reserve r
            LEFT JOIN parking p ON r.Cell_id = p.Cell_id
            WHERE r.enStat = 1
            ORDER BY r.Resid DESC
            LIMIT 1
        """)

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return jsonify({"res_id": 0}), 200

        return jsonify({
            "res_id": row.get("Resid"),
            "vehNo": row.get("VehNo"),
            "cell_id": row.get("Cell_id"),
            "cell_name": row.get("Cell_Name")
        }), 200

    except Exception as e:
        print(f"Error in latest_slot_assignment: {e}")
        return jsonify({"error": "Internal server error"}), 500


@dashboard_bp.route("/latest_parking_event", methods=["GET"])
def latest_parking_event():
    """Latest enStat=3 event for voice announcements"""
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartparking"
        )
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT r.Resid, r.VehNo, r.Cell_id, p.Cell_Name
            FROM reserve r
            LEFT JOIN parking p ON r.Cell_id = p.Cell_id
            WHERE r.enStat = 3
            ORDER BY r.Resid DESC
            LIMIT 1
        """)

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return jsonify({"res_id": 0}), 200

        return jsonify({
            "res_id": row.get("Resid"),
            "vehNo": row.get("VehNo"),
            "cell_id": row.get("Cell_id"),
            "cell_name": row.get("Cell_Name")
        }), 200

    except Exception as e:
        print(f"Error in latest_parking_event: {e}")
        return jsonify({"error": "Internal server error"}), 500


@dashboard_bp.route("/latest_exit_event", methods=["GET"])
def latest_exit_event():
    """Latest exStat=4 event for voice announcements"""
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="smartparking"
        )
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT r.Resid, r.VehNo, r.Cell_id, p.Cell_Name
            FROM reserve r
            LEFT JOIN parking p ON r.Cell_id = p.Cell_id
            WHERE r.exStat = 4
            ORDER BY r.Resid DESC
            LIMIT 1
        """)

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return jsonify({"res_id": 0}), 200

        return jsonify({
            "res_id": row.get("Resid"),
            "vehNo": row.get("VehNo"),
            "cell_id": row.get("Cell_id"),
            "cell_name": row.get("Cell_Name")
        }), 200

    except Exception as e:
        print(f"Error in latest_exit_event: {e}")
        return jsonify({"error": "Internal server error"}), 500
