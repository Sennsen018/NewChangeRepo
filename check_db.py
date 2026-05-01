import mysql.connector
from Main.__init__ import db_config

def check_schema():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        print("Schema for Submitted_Reports:")
        cursor.execute("DESCRIBE Submitted_Reports")
        for row in cursor.fetchall():
            print(row)
            
        print("\nChecking for any potentially broken pages...")
        # Check if attendance_analytics template exists (done)
        # Check if all links in sidebar are valid
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_schema()
