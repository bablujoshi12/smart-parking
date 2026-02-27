"""
Database Utilities Module
Common database functions used across different modules
"""
import mysql.connector

def get_db_connection():
    """Get database connection"""
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="smartparking"
    )

def check_parking_space():
    """Check if parking space is available"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Execute the query
        cursor.execute("SELECT COUNT(Cell_id) FROM parking WHERE status = 0;")
        result = cursor.fetchone()
        
        # Extract count value
        count = result[0] if result else 0
        
        # Return message based on count
        if count == 0:
            return False
        else:
            return True
            
    except mysql.connector.Error as err:
        return f"Database error: {err}"
    finally:
        # Close connections properly
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

def check_already_allocated(phone: int):
    """Check if phone number already has allocated parking"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Execute the query
        cursor.callproc("CheckAlreadyRegistered", [phone])
        result = None
        for result_set in cursor.stored_results():
            result = result_set.fetchone()
            break
            
        return result
        
    except mysql.connector.Error as err:
        return f"Database error: {err}"
    finally:
        # Close connections properly
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()
