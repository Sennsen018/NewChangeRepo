import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def list_students():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT', '6543')
        )
        cur = conn.cursor()
        cur.execute("SELECT usid, first_name, last_name, status FROM Students ORDER BY usid DESC LIMIT 30")
        rows = cur.fetchall()
        for row in rows:
            print(row)
        cur.close()
        conn.close()
    except Exception as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    list_students()
