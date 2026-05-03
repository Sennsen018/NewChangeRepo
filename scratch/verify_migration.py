import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def verify():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT')
        )
        cursor = conn.cursor()
        
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'enrollments';")
        columns = [row[0] for row in cursor.fetchall()]
        print(f"Columns in Enrollments: {columns}")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Verification failed: {e}")

if __name__ == "__main__":
    verify()
