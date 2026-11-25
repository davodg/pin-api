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
        await service.create(payload)
        fake_repo.create.assert_awaited_once_with(payload)
        await service.get(1, 10, {'id': 'x'})
        fake_repo.get.assert_awaited_with(1, 10, {'id': 'x'})
        await service.delete('abc')
        fake_repo.delete.assert_awaited_with('abc')
        await service.update('xyz', payload)
        fake_repo.update.assert_awaited_with('xyz', payload)


class TestFastApiEndpoints(unittest.TestCase):
    def setUp(self):
        api_main.app.dependency_overrides[api_main.get_current_user] = lambda: {'role': 'admin'}
        self.svc = mock.AsyncMock()
        api_main.app.dependency_overrides[api_main.get_feedback_service] = lambda: self.svc
        self.addCleanup(api_main.app.dependency_overrides.clear)
        self.client = TestClient(api_main.app)
        self.addCleanup(self.client.close)

    def test_health_endpoint(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'ok')
        self.assertIn('app', body)
        self.assertIn('env', body)

    def test_create_feedback_route(self):
        svc = self.svc
        svc.create.return_value = {'data': {'id': 1}}
        payload = {'name': 'Test'}
        response = self.client.post('/api/v1/feedback', json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'data': {'id': 1}})
        svc.create.assert_awaited_once_with(payload)

    def test_get_feedback_route(self):
        svc = self.svc
        svc.get.return_value = {'data': [], 'meta': {}}
        response = self.client.get('/api/v1/feedback?page=1&limit=5')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'data': [], 'meta': {}})
        svc.get.assert_awaited_once()

    def test_delete_feedback_route(self):
        svc = self.svc
        svc.delete.return_value = {'data': {'id': '99'}}
        response = self.client.delete('/api/v1/feedback/99')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'data': {'id': '99'}})
        svc.delete.assert_awaited_once_with('99')

    def test_update_feedback_route(self):
        svc = self.svc
        svc.update.return_value = {'data': {'id': '77', 'name': 'Updated'}}
        payload = {'name': 'Updated'}
        response = self.client.put('/api/v1/feedback/77', json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'data': {'id': '77', 'name': 'Updated'}})
        svc.update.assert_awaited_once_with('77', payload)
