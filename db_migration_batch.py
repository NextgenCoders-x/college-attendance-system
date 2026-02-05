import mysql.connector
from config import Config

def migrate():
    try:
        print("Connecting to database...")
        db = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            autocommit=True
        )
        cursor = db.cursor()

        print("Altering STUDENTS table...")
        try:
            cursor.execute("ALTER TABLE students MODIFY section VARCHAR(20) NOT NULL")
            print("Successfully altered students.section to VARCHAR(20)")
        except mysql.connector.Error as err:
            print(f"Index error or already exists (ignoring): {err}")

        print("Altering SUBJECTS table...")
        try:
            cursor.execute("ALTER TABLE subjects MODIFY section VARCHAR(20) NOT NULL")
            print("Successfully altered subjects.section to VARCHAR(20)")
        except mysql.connector.Error as err:
            print(f"Index error or already exists (ignoring): {err}")

        print("Updating existing STUDENT data...")
        cursor.execute("UPDATE students SET section = 'I Batch' WHERE section IN ('A', 'B', 'C', '')")
        print(f"Updated {cursor.rowcount} students.")

        print("Updating existing SUBJECT data...")
        cursor.execute("UPDATE subjects SET section = 'I Batch' WHERE section IN ('A', 'B', 'C', '')")
        print(f"Updated {cursor.rowcount} subjects.")

        db.close()
        print("Migration complete.")

    except Exception as e:
        print(f"Migration Failed: {e}")

if __name__ == "__main__":
    migrate()
