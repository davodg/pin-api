import hashlib
import json

from psycopg.errors import LockNotAvailable
from app.models.employee_feedback import (FeedbackEnvelope, FeedbackResponse,
    FeedbackBatchCreate, FeedbackBatchResponse, FeedbackBatchItem, FeedbackBatchMeta)
from app.repositories.idempotency_repository import (
    IdempotencyRepository, IdempotencyBusy, StoredResponse,
)
from uuid import UUID

from app.models.employee_feedback import FeedbackCreate, FeedbackReplace, FeedbackUpdate
from app.repositories.feedback_repository import FeedbackRepository

class FeedbackService(object):
    def __init__(self, repository: FeedbackRepository):
        self.repository = repository

    async def create(self, feedback: FeedbackCreate, user_id: UUID, key: str):
        async def create_response(repository):
            result = await repository.create(feedback)
            return FeedbackEnvelope[FeedbackResponse].model_validate(result)

        return await self._create_idempotent(
            feedback, user_id, key, 'feedback:create:v1', create_response,
        )

    async def create_batch(self, batch: FeedbackBatchCreate, user_id: UUID, key: str):
        async def create_response(repository):
            items = []
            # All writes share the borrowed connection and its outer transaction.
            for index, feedback in enumerate(batch.items):
                result = await repository.create(feedback)
                items.append(FeedbackBatchItem(index=index, id=result['data'].id))
            return FeedbackBatchResponse(data=items, meta=FeedbackBatchMeta(created=len(items)))

        return await self._create_idempotent(
            batch, user_id, key, 'feedback:batch-create:v1', create_response,
        )

    async def _create_idempotent(self, feedback, user_id, key, operation, create_response):
        canonical = json.dumps(feedback.model_dump(mode='json'), sort_keys=True,
                               separators=(',', ':'), ensure_ascii=False)
        request_hash = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        try:
            async with self.repository.db.transaction() as transaction:
                await transaction.execute("SET LOCAL lock_timeout = '3s'")
                records = IdempotencyRepository(transaction, operation=operation)
                saved = await records.reserve(user_id, key, request_hash)
                if saved is not None:
                    return saved
                result = await create_response(FeedbackRepository(transaction))
                # Serialize before commit, so failures roll back all writes.
                body = result.model_dump(mode='json')
                response = StoredResponse(200, body)
                await records.complete(user_id, key, request_hash, response)
                return response
        except LockNotAvailable as exc:
            raise IdempotencyBusy() from exc

    async def get(self, page, limit, filters=None):
        return await self.repository.get(page, limit, filters)

    async def delete(self, feedback_id):
        return await self.repository.delete(feedback_id)

    async def update(self, feedback_id: UUID, feedback: FeedbackReplace):
        return await self.repository.update(feedback_id, feedback)

    async def patch(self, feedback_id: UUID, feedback: FeedbackUpdate):
        return await self.repository.patch(feedback_id, feedback)
