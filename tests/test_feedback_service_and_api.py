import unittest
import pathlib
import sys
import types
from unittest import mock


ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]
PIN_API_DIR = ROOT_DIR
UNDERSCORE_API_DIR = ROOT_DIR.parent / 'pin_api'
for p in [str(PIN_API_DIR), str(UNDERSCORE_API_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

if 'psycopg2cffi' not in sys.modules:
    class _DummyCursor:
        def execute(self, *args, **kwargs):
            return None
        def fetchall(self):
            return []
    class _DummyConnection:
        def cursor(self):
            return _DummyCursor()
        def commit(self):
            pass
        def rollback(self):
            pass
        def close(self):
            pass
    fake_psycopg2 = types.SimpleNamespace(connect=lambda *args, **kwargs: _DummyConnection())
    sys.modules['psycopg2cffi'] = fake_psycopg2

from app.services.feedback_service import FeedbackService
from fastapi.testclient import TestClient
import main as api_main


class TestFeedbackService(unittest.TestCase):

    def test_service_delegates_methods(self):
        fake_repo = mock.MagicMock()
        with mock.patch('app.services.feedback_service.FeedbackRepository', return_value=fake_repo):
            service = FeedbackService()
            payload = {'foo': 'bar'}
            service.create(payload)
            fake_repo.create.assert_called_once_with(payload)
            service.get(1, 10, {'id': 'x'})
            fake_repo.get.assert_called_with(1, 10, {'id': 'x'})
            service.delete('abc')
            fake_repo.delete.assert_called_with('abc')
            service.update('xyz', payload)
            fake_repo.update.assert_called_with('xyz', payload)


class TestFastApiEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api_main.app)

    def test_health_endpoint(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'ok')
        self.assertIn('app', body)
        self.assertIn('env', body)

    def test_create_feedback_route(self):
        with mock.patch.object(api_main, 'feedback_service') as svc:
            svc.create.return_value = {'data': {'id': 1}}
            payload = {'name': 'Test'}
            response = self.client.post('/api/v1/feedback', json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'data': {'id': 1}})
            svc.create.assert_called_once_with(payload)

    def test_get_feedback_route(self):
        with mock.patch.object(api_main, 'feedback_service') as svc:
            svc.get.return_value = {'data': [], 'meta': {}}
            response = self.client.get('/api/v1/feedback?page=1&limit=5')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'data': [], 'meta': {}})
            svc.get.assert_called_once()

    def test_delete_feedback_route(self):
        with mock.patch.object(api_main, 'feedback_service') as svc:
            svc.delete.return_value = {'data': {'id': '99'}}
            response = self.client.delete('/api/v1/feedback/99')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'data': {'id': '99'}})
            svc.delete.assert_called_once_with('99')

    def test_update_feedback_route(self):
        with mock.patch.object(api_main, 'feedback_service') as svc:
            svc.update.return_value = {'data': {'id': '77', 'name': 'Updated'}}
            payload = {'name': 'Updated'}
            response = self.client.put('/api/v1/feedback/77', json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'data': {'id': '77', 'name': 'Updated'}})
            svc.update.assert_called_once_with('77', payload)