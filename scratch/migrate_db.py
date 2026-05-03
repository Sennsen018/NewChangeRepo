import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def migrate():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT')
        )
        conn.autocommit = True # Use autocommit to avoid massive rollbacks on minor errors
        cursor = conn.cursor()
        
        print("Starting robust migration...")
        
        # 1. Update Teacher_Assignments to add UNIQUE constraint
        print("Step 1: Adding UNIQUE constraint to Teacher_Assignments...")
        try:
            cursor.execute("ALTER TABLE Teacher_Assignments ADD CONSTRAINT unique_teacher_assignment UNIQUE (uTID, subject_id, section);")
        except Exception as e:
            print(f"  Note: {e}")

        # 2. Add assignment_id to Enrollments
        print("Step 2: Adding assignment_id column to Enrollments...")
        try:
            cursor.execute("ALTER TABLE Enrollments ADD COLUMN assignment_id INT;")
        except Exception as e:
            print(f"  Note: {e}")
        
        # 3. Try to populate assignment_id based on subject_id and section
        print("Step 3: Populating assignment_id in Enrollments...")
        try:
            # Check if columns still exist before updating
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'enrollments' AND column_name = 'subject_id';")
            if cursor.fetchone():
                cursor.execute("""
                    UPDATE Enrollments e
                    SET assignment_id = ta.assignment_id
                    FROM Teacher_Assignments ta
                    WHERE e.subject_id = ta.subject_id AND e.section = ta.section;
                """)
                print("  Data populated.")
            else:
                print("  subject_id column already gone, skipping population.")
        except Exception as e:
            print(f"  Error populating data: {e}")
        
        # 4. Add constraints to Enrollments
        print("Step 4: Adding constraints to Enrollments...")
        try:
            cursor.execute("ALTER TABLE Enrollments ADD CONSTRAINT fk_enrollment_assignment FOREIGN KEY (assignment_id) REFERENCES Teacher_Assignments(assignment_id) ON DELETE CASCADE;")
        except Exception as e:
            print(f"  Note (FK): {e}")
            
        try:
            cursor.execute("ALTER TABLE Enrollments ADD CONSTRAINT unique_enrollment UNIQUE (uSID, assignment_id);")
        except Exception as e:
            print(f"  Note (Unique): {e}")

        # 5. Remove old columns from Enrollments
        print("Step 5: Removing old columns from Enrollments...")
        try:
            cursor.execute("ALTER TABLE Enrollments DROP COLUMN IF EXISTS subject_id;")
            cursor.execute("ALTER TABLE Enrollments DROP COLUMN IF EXISTS section;")
        except Exception as e:
            print(f"  Note (Drop): {e}")

        print("Migration process finished.")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Migration failed at connection level: {e}")

if __name__ == "__main__":
    migrate()
