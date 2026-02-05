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

        print("Altering STUDENTS table to add admin_override_percentage...")
        try:
            cursor.execute("ALTER TABLE students ADD COLUMN admin_override_percentage FLOAT DEFAULT NULL")
            print("Successfully added admin_override_percentage column.")
        except mysql.connector.Error as err:
            # Check if column already exists (Error 1060)
            if err.errno == 1060:
                print("Column admin_override_percentage already exists.")
            else:
                print(f"Error: {err}")

        db.close()
        print("Migration complete.")

    except Exception as e:
        print(f"Migration Failed: {e}")

if __name__ == "__main__":
    migrate()
