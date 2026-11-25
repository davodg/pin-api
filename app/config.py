import os
from dotenv import load_dotenv

load_dotenv()

class Config(object):
    def __init__(self):
        self.postgres_db_user = os.getenv('DB_USER')
        self.postgres_db_password = os.getenv('DB_PASSWORD')
        self.postgres_db_host = os.getenv('DB_HOST')
        self.postgres_db_port = os.getenv('DB_PORT')
        self.postgres_db_name = os.getenv('DB_NAME')
        self.jwt_secret = os.getenv('JWT_SECRET', '')
        self.jwt_issuer = 'pin-api'
        self.jwt_audience = 'pin-api'

    def validate_auth(self):
        if len(self.jwt_secret.encode()) < 32:
            raise ValueError('JWT_SECRET must be set to a random secret of at least 32 bytes')
