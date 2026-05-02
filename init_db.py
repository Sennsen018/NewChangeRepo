import psycopg2
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

def init_db():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT')
        )
        cursor = conn.cursor()
        
        # Read the SQL file
        with open('database.sql', 'r') as f:
            sql_script = f.read()
        
        print("Executing database.sql...")
        cursor.execute(sql_script)
        
        # Insert/Update the admin user provided by the user
        admin_user = 'admin1'
        admin_pass = 'password123'
        admin_email = 'admin@atendeez.com'
        hashed_pass = generate_password_hash(admin_pass)
        
        print(f"Ensuring admin user '{admin_user}' exists...")
        cursor.execute("""
            INSERT INTO Admins (username, password_hash, email)
            VALUES (%s, %s, %s)
            ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash
        """, (admin_user, hashed_pass, admin_email))
        
        conn.commit()
        print("Database initialized successfully!")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error initializing database: {e}")

if __name__ == "__main__":
    init_db()
