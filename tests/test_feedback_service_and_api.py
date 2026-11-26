import unittest
import pathlib
import sys
from unittest import mock


ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
PIN_API_DIR = ROOT_DIR
UNDERSCORE_API_DIR = ROOT_DIR.parent / 'pin_api'
for p in [str(PIN_API_DIR), str(UNDERSCORE_API_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)


from app.services.feedback_service import FeedbackService
from fastapi.testclient import TestClient
import main as api_main


class TestFeedbackService(unittest.IsolatedAsyncioTestCase):

    async def test_service_delegates_methods(self):
        fake_repo = mock.AsyncMock()
        service = FeedbackService(fake_repo)
        payload = {'foo': 'bar'}
        await service.get(1, 10, {'id': 'x'})
        fake_repo.get.assert_awaited_with(1, 10, {'id': 'x'})
        await service.delete('abc')
        fake_repo.delete.assert_awaited_with('abc')
        await service.update('xyz', payload)
        fake_repo.update.assert_awaited_with('xyz', payload)
        await service.patch('xyz', payload)
        fake_repo.patch.assert_awaited_once_with('xyz', payload)


from app.repositories.idempotency_repository import StoredResponse, IdempotencyConflict, IdempotencyBusy
from tests.feedback_fixtures import FEEDBACK_ID, payload, record
from app.models.employee_feedback import FeedbackCreate, FeedbackReplace, FeedbackUpdate
from app.repositories.feedback_repository import FeedbackNotFound


class TestFastApiEndpoints(unittest.TestCase):
    def setUp(self):
        api_main.app.dependency_overrides[api_main.get_current_user] = lambda: {'role': 'admin', 'id': FEEDBACK_ID}
        self.svc = mock.AsyncMock()
        api_main.app.dependency_overrides[api_main.get_feedback_service] = lambda: self.svc
        self.addCleanup(api_main.app.dependency_overrides.clear)
        self.client = TestClient(api_main.app, headers={'Idempotency-Key': 'test-key'})
        self.addCleanup(self.client.close)
        self.url = f'/api/v1/feedback/{FEEDBACK_ID}'
        for method in ['create', 'update', 'patch']:
            getattr(self.svc, method).return_value = {'data': record(), 'meta': {}}

        self.svc.create.return_value = StoredResponse(200, {'data': record().model_dump(mode='json'), 'meta': {}})

    def test_create_typed_payload_and_response(self):
        response = self.client.post('/api/v1/feedback', json=payload(response_date='2024-01-20'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['id'], str(FEEDBACK_ID))
        self.assertEqual(response.json()['meta'], {})
        self.svc.create.assert_awaited_once_with(FeedbackCreate(**payload(response_date='2024-01-20')), FEEDBACK_ID, 'test-key')

    def test_get_feedback_route(self):
        self.svc.get.return_value = {'data': [record(response_date='2024-01-20')], 'meta': {'total': 1}}
        response = self.client.get('/api/v1/feedback?page=2&limit=5')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data'][0]['response_date'], '2024-01-20')
        self.assertEqual(self.svc.get.await_args.args[:2], (2, 5))

    def test_get_by_id_response(self):
        for data in [record(), None]:
            self.svc.get.return_value = {'data': data, 'meta': {}}
            response = self.client.get('/api/v1/feedback', params={'id': str(FEEDBACK_ID)})
            self.assertEqual(response.status_code, 200)

    def test_replace_and_patch_typed_payloads(self):
        self.assertEqual(self.client.put(self.url, json=payload()).status_code, 200)
        self.svc.update.assert_awaited_once_with(FEEDBACK_ID, FeedbackReplace(**payload()))
        self.assertEqual(self.client.patch(self.url, json={'name': 'Changed'}).status_code, 200)
        self.svc.patch.assert_awaited_once_with(FEEDBACK_ID, FeedbackUpdate(name='Changed'))

    def test_delete(self):
        self.svc.delete.return_value = {'data': {'id': FEEDBACK_ID}, 'meta': {}}
        response = self.client.delete(self.url)
        self.assertEqual(response.status_code, 200)
        self.svc.delete.assert_awaited_once_with(FEEDBACK_ID)

    def test_invalid_payloads_never_reach_service(self):
        cases = [{}, {'name': 'Only name'}, payload(email='invalid'), payload(name='   '),
                 payload(name='x'*256), payload(enps=True), payload(enps='8'),
                 payload(enps=1.5), payload(unknown='value'), payload(id=str(FEEDBACK_ID)),
                 payload(response_date='20/01/2024'), payload(response_date=1700000000)]
        for data in cases:
            for method, path in [('post', '/api/v1/feedback'), ('put', self.url)]:
                with self.subTest(method=method, data=data):
                    self.assertEqual(self.client.request(method, path, json=data).status_code, 422)
        self.svc.create.assert_not_awaited()
        self.svc.update.assert_not_awaited()

    def test_patch_invalid_nulls_unknown_and_empty(self):
        for data in [{}, {'name': None}, {'enps': None}, {'email': 'invalid'}, {'id': str(FEEDBACK_ID)}]:
            self.assertEqual(self.client.patch(self.url, json=data).status_code, 422)
        self.svc.patch.assert_not_awaited()
        self.assertEqual(self.client.patch(self.url, json={'feedback_comments': None}).status_code, 200)

    def test_invalid_ids_and_pagination(self):
        for params in [{'id': 'invalid'}, {'page': 0}, {'limit': 0}, {'limit': 101}]:
            self.assertEqual(self.client.get('/api/v1/feedback', params=params).status_code, 422)
        self.assertEqual(self.client.delete('/api/v1/feedback/invalid').status_code, 422)
        self.svc.get.assert_not_awaited()
        self.svc.delete.assert_not_awaited()

    def test_missing_write_targets_return_404(self):
        for method in ['update', 'patch', 'delete']:
            getattr(self.svc, method).side_effect = FeedbackNotFound()
        for method, data in [('put', payload()), ('patch', {'name': 'Changed'}), ('delete', None)]:
            response = self.client.request(method, self.url, json=data)
            self.assertEqual(response.status_code, 404)

    def test_idempotency_header_is_required_and_validated(self):
        self.client.headers.pop('Idempotency-Key')
        for headers in [{}, {'Idempotency-Key': ''}, {'Idempotency-Key': 'bad key'},
                        {'Idempotency-Key': 'x' * 129}]:
            response = self.client.post('/api/v1/feedback', headers=headers, json=payload())
            self.assertEqual(response.status_code, 422)
        self.svc.create.assert_not_awaited()

    def test_idempotency_errors(self):
        for error, status in [(IdempotencyConflict(), 409), (IdempotencyBusy(), 503)]:
            self.svc.create.side_effect = error
            response = self.client.post('/api/v1/feedback', json=payload())
            self.assertEqual(response.status_code, status)
            if status == 503:
                self.assertEqual(response.headers['retry-after'], '1')
