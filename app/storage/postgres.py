from app.config import Config
import psycopg2cffi

class Postgres:
    def __init__(self):
        self.config = Config()
        self.conn = psycopg2cffi.connect(
            user=self.config.postgres_db_user,
            password=self.config.postgres_db_password,
            host=self.config.postgres_db_host,
            port=self.config.postgres_db_port,
            database=self.config.postgres_db_name,
        )
        self.cursor = self.conn.cursor()

    def query(self, sql, params=None):
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params or ())
                rows = cur.fetchall()
                return rows
        except Exception:
            self.conn.rollback()
            raise

    def execute(self, query, values=''):
        try:
            self.cursor.execute(query, values)
            self.conn.commit()
            return self.cursor.fetchall() if 'RETURNING' in query.upper() else None
        except Exception:
            self.conn.rollback()
            raise

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
