import unittest
from unittest import mock

from fastapi.testclient import TestClient

import main
from app.models.employee_feedback import FeedbackBatchCreate
from app.repositories.idempotency_repository import StoredResponse, IdempotencyConflict, IdempotencyBusy
from tests.feedback_fixtures import FEEDBACK_ID, payload


class TestFeedbackBatch(unittest.TestCase):
    def setUp(self):
        self.user = {'id': FEEDBACK_ID, 'role': 'admin'}
        self.service = mock.AsyncMock()
        self.body = {'data': [{'index': 0, 'id': str(FEEDBACK_ID)}], 'meta': {'created': 1}}
        self.service.create_batch.return_value = StoredResponse(200, self.body)
        main.app.dependency_overrides[main.get_current_user] = lambda: self.user
        main.app.dependency_overrides[main.get_feedback_service] = lambda: self.service
        self.addCleanup(main.app.dependency_overrides.clear)
        self.client = TestClient(main.app, headers={'Idempotency-Key': 'batch-key'})
        self.addCleanup(self.client.close)
        self.url = '/api/v1/feedback/batch'

    def test_success_passes_validated_batch_and_user(self):
        response = self.client.post(self.url, json={'items': [payload()]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), self.body)
        self.service.create_batch.assert_awaited_once_with(
            FeedbackBatchCreate(items=[payload()]), FEEDBACK_ID, 'batch-key')

    def test_one_to_one_hundred_items(self):
        for count, status in [(0, 422), (1, 200), (100, 200), (101, 422)]:
            self.service.create_batch.reset_mock()
            response = self.client.post(self.url, json={'items': [payload()] * count})
            self.assertEqual(response.status_code, status)
            if status == 422:
                self.service.create_batch.assert_not_awaited()

    def test_invalid_item_is_indexed_and_no_service_call(self):
        response = self.client.post(self.url, json={'items': [payload(), payload(email='invalid')]})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['detail'][0]['loc'], ['body', 'items', 1, 'email'])
        self.service.create_batch.assert_not_awaited()

    def test_malformed_batches(self):
        for body in [{}, {'items': None}, {'items': [None]}, {'items': [payload()], 'extra': 1}]:
            self.assertEqual(self.client.post(self.url, json=body).status_code, 422)
        self.service.create_batch.assert_not_awaited()

    def test_key_validation(self):
        self.client.headers.pop('Idempotency-Key')
        for headers in [{}, {'Idempotency-Key': ''}, {'Idempotency-Key': 'bad key'}, {'Idempotency-Key': 'x'*129}]:
            self.assertEqual(self.client.post(self.url, json={'items': [payload()]}, headers=headers).status_code, 422)
        self.service.create_batch.assert_not_awaited()

    def test_viewer_cannot_create_or_replay(self):
        self.assertEqual(self.client.post(self.url, json={'items': [payload()]}).status_code, 200)
        self.service.create_batch.reset_mock()
        self.user['role'] = 'viewer'
        self.assertEqual(self.client.post(self.url, json={'items': [payload()]}).status_code, 403)
        self.service.create_batch.assert_not_awaited()

    def test_conflict_and_timeout(self):
        for error, code in [(IdempotencyConflict(), 409), (IdempotencyBusy(), 503)]:
            self.service.create_batch.side_effect = error
            response = self.client.post(self.url, json={'items': [payload()]})
            self.assertEqual(response.status_code, code)
            if code == 503:
                self.assertEqual(response.headers['retry-after'], '1')
