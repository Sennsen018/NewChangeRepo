import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT', '5432')
        )
        return conn
    except Exception as err:
        print(f"Error connecting to DB: {err}")
        return None

def log_system_action(cursor, table_name, entity_id, action, performed_by_id, performed_by_role, details=None):
    """
    Logs a system action (Create, Update, Delete) into the System_Audit_Log table.
    """
    try:
        cursor.execute("""
            INSERT INTO System_Audit_Log (table_name, entity_id, action, performed_by_id, performed_by_role, details)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (table_name, str(entity_id), action, str(performed_by_id), performed_by_role, details))
    except Exception as e:
        print(f"Failed to log system action: {e}")
