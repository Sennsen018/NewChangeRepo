import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def check_admins():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT', '6543')
        )
        cur = conn.cursor()
        cur.execute("SELECT * FROM admins")
        rows = cur.fetchall()
        for row in rows:
            print(row)
        cur.close()
        conn.close()
    except Exception as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    check_admins()
