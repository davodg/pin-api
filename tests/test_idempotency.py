import unittest
from unittest import mock

from app.models.employee_feedback import FeedbackCreate
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.idempotency_repository import IdempotencyRepository, IdempotencyConflict, StoredResponse
from app.services.feedback_service import FeedbackService
from tests.feedback_fixtures import FEEDBACK_ID, payload, record


class TestIdempotency(unittest.IsolatedAsyncioTestCase):
    async def test_reservation_returns_original_response(self):
        db = mock.AsyncMock()
        db.execute.return_value = [('hash', 200, {'data': {'id': 'original'}}, False)]
        repo = IdempotencyRepository(db)
        result = await repo.reserve(FEEDBACK_ID, 'key', 'hash')
        self.assertEqual(result, StoredResponse(200, {'data': {'id': 'original'}}))
        with self.assertRaises(IdempotencyConflict):
            await repo.reserve(FEEDBACK_ID, 'key', 'different')

    async def test_new_and_expired_reservations_can_execute(self):
        db = mock.AsyncMock()
        repo = IdempotencyRepository(db)
        for row in [('new', None, None, False), ('old', 200, {}, True)]:
            db.execute.return_value = [row]
            self.assertIsNone(await repo.reserve(FEEDBACK_ID, 'key', 'new'))

    async def test_canonical_payload_and_replay_skip_creation(self):
        db = mock.MagicMock()
        transaction = db.transaction.return_value.__aenter__.return_value
        service = FeedbackService(FeedbackRepository(db))
        saved = StoredResponse(200, {'data': record().model_dump(mode='json'), 'meta': {}})
        records = mock.AsyncMock()
        records.reserve.return_value = saved
        with mock.patch('app.services.feedback_service.IdempotencyRepository', return_value=records):
            a = await service.create(FeedbackCreate(**payload()), FEEDBACK_ID, 'key')
            hash_a = records.reserve.await_args.args[2]
            b = await service.create(FeedbackCreate(**dict(reversed(list(payload(feedback_comments=None).items())))), FEEDBACK_ID, 'key')
            self.assertEqual(hash_a, records.reserve.await_args.args[2])
            self.assertEqual(a, b)
            records.complete.assert_not_awaited()
            self.assertEqual(transaction.execute.await_count, 2)  # SET LOCAL only

    async def test_creation_and_response_use_same_transaction(self):
        db = mock.MagicMock()
        transaction = db.transaction.return_value.__aenter__.return_value
        service = FeedbackService(FeedbackRepository(db))
        records = mock.AsyncMock()
        records.reserve.return_value = None
        feedback_repo = mock.AsyncMock()
        feedback_repo.create.return_value = {'data': record(), 'meta': {}}
        with mock.patch('app.services.feedback_service.IdempotencyRepository', return_value=records) as ids, \
             mock.patch('app.services.feedback_service.FeedbackRepository', return_value=feedback_repo) as feedbacks:
            response = await service.create(FeedbackCreate(**payload()), FEEDBACK_ID, 'key')
            ids.assert_called_once_with(transaction, operation='feedback:create:v1')
            feedbacks.assert_called_once_with(transaction)
            records.complete.assert_awaited_once()
            self.assertEqual(response.body['data']['id'], str(FEEDBACK_ID))
        db.transaction.return_value.__aexit__.assert_awaited_once_with(None, None, None)
