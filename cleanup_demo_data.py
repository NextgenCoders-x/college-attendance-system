import mysql.connector
from config import Config

def cleanup_data():
    try:
        db = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            autocommit=True
        )
        cursor = db.cursor()
        
        print("Starting cleanup of demo credentials...")
        
        # 1. Delete all class logins
        cursor.execute("DELETE FROM class_logins")
        print(f"Deleted {cursor.rowcount} records from 'class_logins'.")
        
        # 2. Delete all staff profiles
        cursor.execute("DELETE FROM staff")
        print(f"Deleted {cursor.rowcount} records from 'staff'.")
        
        # 3. Delete all users with role 'staff' (This cleans up the login credentials)
        # Note: Even if CASCADE existed, this ensures orphans are gone.
        cursor.execute("DELETE FROM users WHERE role = 'staff'")
        print(f"Deleted {cursor.rowcount} records from 'users' (role='staff').")
        
        print("Cleanup complete.")
        
        db.commit()
        cursor.close()
        db.close()
    except Exception as e:
        print(f"Error during cleanup: {e}")

if __name__ == "__main__":
    cleanup_data()
