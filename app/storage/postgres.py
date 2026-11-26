from contextlib import asynccontextmanager

from psycopg_pool import AsyncConnectionPool

from app.config import Config


class Postgres:
    def __init__(self):
        config = Config()
        self.pool = AsyncConnectionPool(
            kwargs={
                "user": config.postgres_db_user,
                "password": config.postgres_db_password,
                "host": config.postgres_db_host,
                "port": config.postgres_db_port,
                "dbname": config.postgres_db_name,
            },
            min_size=4,
            max_size=16,
            open=False,
        )

    async def open(self):
        await self.pool.open(wait=True)

    async def query(self, sql, params=None):
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                return await cur.fetchall()

    async def execute(self, query, values=None):
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, values)
                return await cur.fetchall() if cur.description is not None else None

    @asynccontextmanager
    async def transaction(self):
        async with self.pool.connection() as conn:
            yield PostgresTransaction(conn)

    async def close(self):
        await self.pool.close()


class PostgresTransaction:
    """Queries on a borrowed connection; only the outer context commits/rolls back."""

    def __init__(self, connection):
        self.connection = connection

    async def execute(self, query, values=None):
        async with self.connection.cursor() as cur:
            await cur.execute(query, values)
            return await cur.fetchall() if cur.description is not None else None

    async def query(self, query, params=None):
        async with self.connection.cursor() as cur:
            await cur.execute(query, params)
            return await cur.fetchall()
