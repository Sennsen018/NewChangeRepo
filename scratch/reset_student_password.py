import psycopg2
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

def reset_password():
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
        new_password = 'password123'
        hashed_pw = generate_password_hash(new_password)
        
        print(f"Updating password for {usid} to {new_password}...")
        cur.execute("UPDATE Students SET password_hash = %s WHERE usid = %s", (hashed_pw, usid))
        conn.commit()
        
        if cur.rowcount > 0:
            print("Successfully updated password.")
        else:
            print("Failed to update password. User might not exist.")
            
        cur.close()
        conn.close()
    except Exception as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    reset_password()
