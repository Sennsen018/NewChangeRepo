import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def apply_triggers():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT')
        )
        cursor = conn.cursor()
        
        print("Applying triggers from triggers.sql...")
        with open('triggers.sql', 'r') as f:
            sql_script = f.read()
            
        cursor.execute(sql_script)
        conn.commit()
        print("Triggers applied successfully!")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error applying triggers: {e}")

if __name__ == "__main__":
    apply_triggers()
