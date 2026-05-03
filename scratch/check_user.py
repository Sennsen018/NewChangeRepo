import psycopg2
import os
from dotenv import load_dotenv
from werkzeug.security import check_password_hash

load_dotenv()

def check_user():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT', '5432')
        )
        cur = conn.cursor()
        
        usid = 'S-2026-008'
        password_to_check = 'password123'
        
        print(f"Checking user {usid}...")
        
        cur.execute("SELECT usid, password_hash, status, first_name, last_name FROM Students WHERE usid = %s", (usid,))
        student = cur.fetchone()
        
        if student:
            print(f"User Found: {student}")
            stored_hash = student[1]
            status = student[2]
            
            if stored_hash:
                # Try comparing directly first (if not hashed)
                if stored_hash == password_to_check:
                    print("Password matches directly (Plaintext).")
                else:
                    # Check if it's a hash
                    is_correct = check_password_hash(stored_hash, password_to_check)
                    if is_correct:
                        print("Password matches via Werkzeug check_password_hash.")
                    else:
                        print("Password does NOT match.")
            else:
                print("No password hash found for this user.")
                
            print(f"User Status: {status}")
            
        else:
            print("User Not Found in Students table.")
            
        cur.close()
        conn.close()
    except Exception as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    check_user()
