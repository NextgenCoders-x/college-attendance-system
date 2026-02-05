import mysql.connector
from config import Config

def migrate_table():
    try:
        db = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            autocommit=True
        )
        cursor = db.cursor()
        
        print("Migrating class_logins table: renaming section to batch...")
        # Check if column exists first to be safe, or just try ALTER
        try:
            cursor.execute("ALTER TABLE class_logins CHANGE section batch VARCHAR(20) NOT NULL")
            print("Successfully renamed 'section' to 'batch'.")
            
            # Update Unique Key if necessary - MySQL might hande column rename in key automatically, 
            # but usually keys need dropping and re-adding if they are named explicitly.
            # Let's check constraints.
            # For simplicity, if it fails, we handle manual key update.
            # The previous key was unique_class_login (department_id, year, section)
            
            # Dropping old key just in case it didn't update (though CHANGE might keep it pointing to new col)
            # cursor.execute("ALTER TABLE class_logins DROP INDEX unique_class_login")
            # cursor.execute("ALTER TABLE class_logins ADD UNIQUE KEY unique_class_login (department_id, year, batch)")
            
        except mysql.connector.Error as err:
            print(f"Migration Error (step 1): {err}")

        db.commit()
        cursor.close()
        db.close()
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    migrate_table()
