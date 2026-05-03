import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def check_data():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT')
        )
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM Enrollments;")
        count = cursor.fetchone()[0]
        print(f"Total enrollments: {count}")
        
        cursor.execute("SELECT COUNT(*) FROM Enrollments WHERE assignment_id IS NULL;")
        null_count = cursor.fetchone()[0]
        print(f"Enrollments with NULL assignment_id: {null_count}")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Check failed: {e}")

if __name__ == "__main__":
    check_data()
