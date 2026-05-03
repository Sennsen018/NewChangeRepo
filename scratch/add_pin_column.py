import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def update_schema():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT', '6543')
        )
        cur = conn.cursor()
        
        # Check if deletion_pin column exists in admins table
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'admins' AND column_name = 'deletion_pin'")
        if not cur.fetchone():
            print("Adding deletion_pin column to admins table...")
            cur.execute("ALTER TABLE admins ADD COLUMN deletion_pin TEXT")
            # Set a default PIN hash (e.g. '1234' -> generate_password_hash('1234'))
            # For simplicity, let's just leave it NULL and handle the setup in UI
            conn.commit()
            print("Column added.")
        else:
            print("Column deletion_pin already exists.")
            
        cur.close()
        conn.close()
    except Exception as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    update_schema()
