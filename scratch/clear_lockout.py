import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def clear_lockout():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT', '6543')
        )
        cur = conn.cursor()
        
        usid = 'S-2026-008'
        print(f"Clearing lockout for {usid}...")
        cur.execute("UPDATE Students SET failed_attempts = 0, lockout_time = NULL WHERE usid = %s", (usid,))
        conn.commit()
        
        print("Done.")
            
        cur.close()
        conn.close()
    except Exception as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    clear_lockout()
