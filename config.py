import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev_key_very_secret_123'
    DB_HOST = 'localhost'
    DB_USER = 'root'
    DB_PASSWORD = 'mohan'
    DB_NAME = 'attendance_db'
