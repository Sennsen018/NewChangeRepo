import mysql.connector
from Main.__init__ import db_config

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
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
