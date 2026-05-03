import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def list_columns():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT', '5432')
        )
        cur = conn.cursor()
        
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'students'")
        print("Columns in 'students':")
        for row in cur.fetchall():
            print(f"- {row[0]}")
            
        cur.close()
        conn.close()
    except Exception as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    list_columns()
