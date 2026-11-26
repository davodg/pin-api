"""Opt-in PostgreSQL tests. Use a disposable DB named pin_test_* and migrate it first."""
import asyncio
import os
import unittest
from unittest import mock
from uuid import uuid4

from app.models.employee_feedback import FeedbackCreate, FeedbackBatchCreate
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.idempotency_repository import IdempotencyRepository, IdempotencyConflict, IdempotencyBusy
from app.repositories.user_repository import UserRepository
from app.services.feedback_service import FeedbackService
from app.storage.postgres import Postgres
from tests.feedback_fixtures import payload


@unittest.skipUnless(os.getenv('PIN_API_INTEGRATION') == '1', 'requires disposable PostgreSQL')
class TestIdempotencyIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if not os.getenv('DB_NAME', '').startswith('pin_test_'):
            raise RuntimeError('Integration tests require a disposable DB_NAME starting with pin_test_')
        self.db = Postgres()
        await self.db.open()
        self.addAsyncCleanup(self.db.close)
        self.user_id, self.other_user = uuid4(), uuid4()
        self.email = f'{uuid4()}@example.com'
        self.feedback = FeedbackCreate(**payload(email=self.email))
        self.service = FeedbackService(FeedbackRepository(self.db))
        self.addAsyncCleanup(self.remove_data)
        for uid in [self.user_id, self.other_user]:
            await UserRepository(self.db).create(uid, str(uid), 'unused-test-hash', 'admin')

    async def remove_data(self):
        await self.db.execute('DELETE FROM employee_feedback WHERE email = %s', (self.email,))
        await self.db.execute('DELETE FROM app_user WHERE id IN (%s, %s)', (self.user_id, self.other_user))

    async def count_feedbacks(self):
        return (await self.db.query('SELECT count(*) FROM employee_feedback WHERE email = %s', (self.email,)))[0][0]

    async def expire(self):
        await self.db.execute("UPDATE idempotency_record SET expires_at = clock_timestamp() - interval '1 second' WHERE user_id = %s", (self.user_id,))

    async def test_concurrent_requests_create_once_and_replay_original(self):
        responses = await asyncio.gather(*(
            self.service.create(self.feedback, self.user_id, 'same-key') for _ in range(12)
        ))
        self.assertTrue(all(r == responses[0] for r in responses))
        self.assertEqual(await self.count_feedbacks(), 1)
        # Replay is the saved response, even if the resource subsequently changes.
        await self.db.execute('UPDATE employee_feedback SET name = %s WHERE email = %s', ('Changed later', self.email))
        self.assertEqual(await self.service.create(self.feedback, self.user_id, 'same-key'), responses[0])

    async def test_payload_conflict_and_user_isolation(self):
        first = await self.service.create(self.feedback, self.user_id, 'same-key')
        changed = FeedbackCreate(**payload(email=self.email, name='Different'))
        with self.assertRaises(IdempotencyConflict):
            await self.service.create(changed, self.user_id, 'same-key')
        second = await self.service.create(changed, self.other_user, 'same-key')
        self.assertNotEqual(first.body['data']['id'], second.body['data']['id'])
        self.assertEqual(await self.count_feedbacks(), 2)

    async def test_failed_response_write_rolls_back_feedback_and_reservation(self):
        with mock.patch.object(IdempotencyRepository, 'complete', side_effect=RuntimeError('simulated failure')):
            with self.assertRaisesRegex(RuntimeError, 'simulated failure'):
                await self.service.create(self.feedback, self.user_id, 'rollback-key')
        self.assertEqual(await self.count_feedbacks(), 0)
        rows = await self.db.query('SELECT count(*) FROM idempotency_record WHERE user_id = %s', (self.user_id,))
        self.assertEqual(rows[0][0], 0)
        await self.service.create(self.feedback, self.user_id, 'rollback-key')
        self.assertEqual(await self.count_feedbacks(), 1)

    async def test_expired_key_is_reused_once_under_concurrency(self):
        first = await self.service.create(self.feedback, self.user_id, 'expired-key')
        await self.expire()
        changed = FeedbackCreate(**payload(email=self.email, name='New operation'))
        responses = await asyncio.gather(*(
            self.service.create(changed, self.user_id, 'expired-key') for _ in range(8)
        ))
        self.assertTrue(all(r == responses[0] for r in responses))
        self.assertNotEqual(first.body['data']['id'], responses[0].body['data']['id'])
        self.assertEqual(await self.count_feedbacks(), 2)

    async def test_lock_timeout_rolls_back_and_allows_retry(self):
        first = await self.service.create(self.feedback, self.user_id, 'locked-key')
        async with self.db.transaction() as transaction:
            await transaction.query('SELECT * FROM idempotency_record WHERE user_id = %s FOR UPDATE', (self.user_id,))
            with self.assertRaises(IdempotencyBusy):
                await self.service.create(self.feedback, self.user_id, 'locked-key')
        self.assertEqual(await self.service.create(self.feedback, self.user_id, 'locked-key'), first)
        self.assertEqual(await self.count_feedbacks(), 1)

    async def test_cleanup_skips_locked_rows_and_preserves_feedbacks(self):
        await self.service.create(self.feedback, self.user_id, 'cleanup-key')
        self.assertEqual(await IdempotencyRepository(self.db).cleanup(), 0)
        await self.expire()
        async with self.db.transaction() as transaction:
            await transaction.query('SELECT * FROM idempotency_record WHERE user_id = %s FOR UPDATE', (self.user_id,))
            self.assertEqual(await IdempotencyRepository(self.db).cleanup(), 0)
        self.assertEqual(await IdempotencyRepository(self.db).cleanup(), 1)
        self.assertEqual(await self.count_feedbacks(), 1)

    async def test_batch_concurrency_order_and_single_operation_isolation(self):
        batch = FeedbackBatchCreate(items=[
            payload(email=self.email, name='First'), payload(email=self.email, name='Second')])
        responses = await asyncio.gather(*(
            self.service.create_batch(batch, self.user_id, 'shared-key') for _ in range(8)))
        self.assertTrue(all(response == responses[0] for response in responses))
        self.assertEqual(await self.count_feedbacks(), 2)
        self.assertEqual(responses[0].body['meta'], {'created': 2})
        for index, item in enumerate(responses[0].body['data']):
            self.assertEqual(item['index'], index)
            rows = await self.db.query('SELECT name FROM employee_feedback WHERE id = %s', (item['id'],))
            self.assertEqual(rows[0][0], ['First', 'Second'][index])
        await self.service.create(self.feedback, self.user_id, 'shared-key')
        self.assertEqual(await self.count_feedbacks(), 3)
        reversed_batch = FeedbackBatchCreate(items=list(reversed(batch.items)))
        with self.assertRaises(IdempotencyConflict):
            await self.service.create_batch(reversed_batch, self.user_id, 'shared-key')
        self.assertEqual(await self.count_feedbacks(), 3)

    async def test_failure_in_second_item_rolls_back_whole_batch(self):
        batch = FeedbackBatchCreate(items=[payload(email=self.email), payload(email=self.email)])
        original = FeedbackRepository.create
        calls = 0

        async def failing_create(repository, feedback):
            nonlocal calls
            calls += 1
            if calls == 2:
                # Real PostgreSQL error after the first item was inserted.
                await repository.db.execute('SELECT 1 / 0')
            return await original(repository, feedback)

        from psycopg.errors import DivisionByZero
        with mock.patch.object(FeedbackRepository, 'create', failing_create):
            with self.assertRaises(DivisionByZero):
                await self.service.create_batch(batch, self.user_id, 'rollback-batch')
        self.assertEqual(await self.count_feedbacks(), 0)
        rows = await self.db.query('SELECT count(*) FROM idempotency_record WHERE user_id = %s', (self.user_id,))
        self.assertEqual(rows[0][0], 0)
        response = await self.service.create_batch(batch, self.user_id, 'rollback-batch')
        self.assertEqual(response.body['meta']['created'], 2)
        self.assertEqual(await self.count_feedbacks(), 2)

    async def test_batch_response_failure_rolls_back_all_items(self):
        batch = FeedbackBatchCreate(items=[payload(email=self.email)] * 3)
        with mock.patch.object(IdempotencyRepository, 'complete', side_effect=RuntimeError('response failure')):
            with self.assertRaises(RuntimeError):
                await self.service.create_batch(batch, self.user_id, 'response-failure')
        self.assertEqual(await self.count_feedbacks(), 0)
        response = await self.service.create_batch(batch, self.user_id, 'response-failure')
        self.assertEqual(response.body['meta']['created'], 3)
        self.assertEqual(await self.count_feedbacks(), 3)

    async def test_batch_accepts_one_hundred_items(self):
        batch = FeedbackBatchCreate(items=[payload(email=self.email)] * 100)
        response = await self.service.create_batch(batch, self.user_id, 'hundred-items')
        self.assertEqual(response.body['meta']['created'], 100)
        self.assertEqual([item['index'] for item in response.body['data']], list(range(100)))
        self.assertEqual(len({item['id'] for item in response.body['data']}), 100)
        self.assertEqual(await self.count_feedbacks(), 100)
