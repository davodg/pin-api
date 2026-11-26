"""Run periodically: python -m app.cleanup_idempotency."""
import asyncio

from app.repositories.idempotency_repository import IdempotencyRepository
from app.storage.postgres import Postgres


async def cleanup():
    db = Postgres()
    total = 0
    try:
        await db.open()
        while True:
            async with db.transaction() as transaction:
                removed = await IdempotencyRepository(transaction).cleanup()
            total += removed
            if removed < 1000:
                break
    finally:
        await db.close()
    print(f'Removed {total} expired idempotency records.')


if __name__ == '__main__':
    asyncio.run(cleanup())
