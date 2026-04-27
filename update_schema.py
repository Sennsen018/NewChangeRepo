import mysql.connector
from Main.__init__ import db_config

def update_schema():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    
    try:
        print("Updating Attendance table schema...")
        # Add columns for monitoring
        cursor.execute("""
            ALTER TABLE Attendance 
            ADD COLUMN IF NOT EXISTS student_lat DECIMAL(10, 8),
            ADD COLUMN IF NOT EXISTS student_lon DECIMAL(11, 8),
            ADD COLUMN IF NOT EXISTS distance_meters FLOAT,
            ADD COLUMN IF NOT EXISTS behavior_flags JSON
        """)
        
        # Add index for faster tracking
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON Attendance(session_id)")
        
        conn.commit()
        print("Schema updated successfully.")
    except Exception as e:
        print(f"Error updating schema: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    update_schema()
