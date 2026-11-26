from dataclasses import dataclass

from psycopg.types.json import Jsonb


class IdempotencyConflict(Exception):
    pass


class IdempotencyBusy(Exception):
    pass


@dataclass(frozen=True)
class StoredResponse:
    status: int
    body: dict


class IdempotencyRepository:
    operation = 'feedback:create:v1'

    def __init__(self, transaction, operation="feedback:create:v1"):
        self.db = transaction
        self.operation = operation

    async def reserve(self, user_id, key, request_hash):
        # The no-op UPDATE acquires a row lock until commit, including on replay.
        # Expiration/reuse and cleanup therefore cannot race with this request.
        rows = await self.db.execute('''
            INSERT INTO idempotency_record
                (user_id, operation, idempotency_key, request_hash)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, operation, idempotency_key)
            DO UPDATE SET idempotency_key = EXCLUDED.idempotency_key
            RETURNING request_hash, response_status, response_body,
                      expires_at <= clock_timestamp()
        ''', (user_id, self.operation, key, request_hash))
        saved_hash, status, body, expired = rows[0]
        if expired or status is None:
            return None
        if saved_hash != request_hash:
            raise IdempotencyConflict()
        return StoredResponse(status, body)

    async def complete(self, user_id, key, request_hash, response):
        await self.db.execute('''
            UPDATE idempotency_record
            SET request_hash = %s, response_status = %s, response_body = %s,
                created_at = clock_timestamp(),
                expires_at = clock_timestamp() + interval '24 hours'
            WHERE user_id = %s AND operation = %s AND idempotency_key = %s
        ''', (request_hash, response.status, Jsonb(response.body), user_id, self.operation, key))

    async def cleanup(self):
        # Bounded batches skip rows used by active requests, including expired reuse.
        rows = await self.db.execute('''
            DELETE FROM idempotency_record WHERE (user_id, operation, idempotency_key) IN (
                SELECT user_id, operation, idempotency_key FROM idempotency_record
                WHERE expires_at <= clock_timestamp()
                ORDER BY expires_at LIMIT 1000 FOR UPDATE SKIP LOCKED
            ) RETURNING idempotency_key
        ''')
        return len(rows)
