import mysql.connector
from config import Config

def create_table():
    try:
        db = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            autocommit=True
        )
        cursor = db.cursor()
        
        print("Creating class_logins table...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS class_logins (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT UNIQUE NOT NULL,
            department_id INT NOT NULL,
            year INT NOT NULL,
            section VARCHAR(20) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE,
            UNIQUE KEY unique_class_login (department_id, year, section)
        );
        """)
        print("Table 'class_logins' created successfully.")
        
        db.commit()
        cursor.close()
        db.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    create_table()
