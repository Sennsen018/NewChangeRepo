import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()

def test_db():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT')
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Try to fetch one student
        cursor.execute("SELECT * FROM Students LIMIT 1")
        student = cursor.fetchone()
        
        if student:
            print("Successfully fetched a student!")
            print(f"Columns: {list(student.keys())}")
        else:
            print("No students found in the database.")
            # Check table existence
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_name = 'students'")
            if cursor.fetchone():
                print("Table 'students' exists.")
                # Check column names
                cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'students'")
                cols = [row['column_name'] for row in cursor.fetchall()]
                print(f"Table 'students' column names: {cols}")
            else:
                print("Table 'students' does NOT exist.")
                
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_db()
