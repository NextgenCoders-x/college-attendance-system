import os

class Config:
    DB_HOST = os.getenv("MYSQLHOST", "localhost")
    DB_USER = os.getenv("MYSQLUSER", "root")
    DB_PASSWORD = os.getenv("MYSQLPASSWORD", "")
    DB_NAME = os.getenv("MYSQLDATABASE", "")
    DB_PORT = int(os.getenv("MYSQLPORT", 3306))
