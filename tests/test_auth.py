import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient

from tests.feedback_fixtures import FEEDBACK_ID, payload, record

import main
from app.config import Config
from app.security.auth import AuthService, get_auth_service, password_hasher


class TestAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = 'demo-password-for-tests'
        cls.password_hash = password_hasher.hash(cls.password)

    def setUp(self):
        self.config = Config()
        self.config.jwt_secret = 'test-secret-not-for-deployment-' * 2
        self.repo = mock.AsyncMock()
        self.user = {'id': uuid4(), 'username': 'demo', 'password_hash': self.password_hash,
                     'role': 'viewer', 'is_active': True}
        self.repo.get_by_username.return_value = self.user
        self.repo.get_by_id.return_value = self.user
        self.repo.allow_login.return_value = True
        self.auth = AuthService(self.repo, self.config, self.password_hash)
        self.feedback = mock.AsyncMock()
        self.feedback.get.return_value = {'data': []}
        for method in ['create', 'update', 'patch']:
            getattr(self.feedback, method).return_value = {'data': record()}
        self.feedback.delete.return_value = {'data': {'id': FEEDBACK_ID}}
        main.app.dependency_overrides[get_auth_service] = lambda: self.auth
        main.app.dependency_overrides[main.get_feedback_service] = lambda: self.feedback
        self.addCleanup(main.app.dependency_overrides.clear)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)

    def headers(self, token=None):
        return {'Authorization': 'Bearer ' + (token or self.auth.issue_token(self.user['id']))}

    def feedback_requests(self, headers=None):
        return [self.client.get('/api/v1/feedback', headers=headers),
                self.client.post('/api/v1/feedback', json=payload(), headers=headers),
                self.client.put(f'/api/v1/feedback/{FEEDBACK_ID}', json=payload(), headers=headers),
                self.client.delete(f'/api/v1/feedback/{FEEDBACK_ID}', headers=headers),
                self.client.patch(f'/api/v1/feedback/{FEEDBACK_ID}', json={'name': 'Changed'}, headers=headers)]

    def test_all_feedback_endpoints_require_authentication(self):
        for response in self.feedback_requests():
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers['www-authenticate'], 'Bearer')
        self.assertEqual(self.feedback.mock_calls, [])

    def test_viewer_can_only_read(self):
        self.assertEqual([r.status_code for r in self.feedback_requests(self.headers())], [200, 403, 403, 403, 403])
        self.feedback.create.assert_not_awaited()
        self.feedback.update.assert_not_awaited()
        self.feedback.delete.assert_not_awaited()

    def test_admin_can_use_all_feedback_endpoints(self):
        self.user['role'] = 'admin'
        self.assertEqual([r.status_code for r in self.feedback_requests(self.headers())], [200] * 5)

    def test_role_change_is_effective_for_existing_token(self):
        self.user['role'] = 'admin'
        headers = self.headers()
        self.user['role'] = 'viewer'
        self.assertEqual(self.client.delete(f'/api/v1/feedback/{FEEDBACK_ID}', headers=headers).status_code, 403)

    def test_inactive_deleted_and_unknown_role_users(self):
        headers = self.headers()
        self.user['is_active'] = False
        self.assertEqual(self.client.get('/api/v1/feedback', headers=headers).status_code, 401)
        self.repo.get_by_id.return_value = None
        self.assertEqual(self.client.get('/api/v1/feedback', headers=headers).status_code, 401)
        self.repo.get_by_id.return_value = self.user
        self.user.update(is_active=True, role='unexpected')
        self.assertEqual(self.client.get('/api/v1/feedback', headers=headers).status_code, 403)

    def test_invalid_tokens(self):
        now = datetime.now(timezone.utc)
        payload = {'sub': str(self.user['id']), 'iat': now, 'exp': now + timedelta(minutes=15),
                   'iss': 'pin-api', 'aud': 'pin-api'}
        cases = [dict(payload, exp=now-timedelta(seconds=1)), dict(payload, iss='other'),
                 dict(payload, aud='other'), dict(payload, sub='invalid'),
                 dict(payload, iat=now+timedelta(hours=1))]
        for claim in payload:
            cases.append({k: v for k, v in payload.items() if k != claim})
        tokens = [jwt.encode(p, self.config.jwt_secret, algorithm='HS256') for p in cases]
        tokens += [jwt.encode(payload, 'wrong-key-' * 8, algorithm='HS256'),
                   jwt.encode(payload, self.config.jwt_secret, algorithm='HS384'),
                   jwt.encode(payload, '', algorithm='none'), 'not.a.token']
        for token in tokens:
            with self.subTest(token=token):
                self.assertEqual(self.client.get('/api/v1/feedback', headers=self.headers(token)).status_code, 401)
        self.repo.get_by_id.assert_not_awaited()

    def test_login_and_token(self):
        response = self.client.post('/auth/token', json={'username': 'demo', 'password': self.password})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['expires_in'], 900)
        self.assertEqual(body['token_type'], 'bearer')
        self.assertEqual(self.client.get('/api/v1/feedback', headers=self.headers(body['access_token'])).status_code, 200)
        self.assertNotIn('password', body)

    def test_invalid_login_is_generic(self):
        responses = [self.client.post('/auth/token', json={'username': 'demo', 'password': 'wrong'})]
        self.user['is_active'] = False
        responses.append(self.client.post('/auth/token', json={'username': 'demo', 'password': self.password}))
        self.repo.get_by_username.return_value = None
        responses.append(self.client.post('/auth/token', json={'username': 'missing', 'password': self.password}))
        for response in responses:
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), {'detail': 'Invalid credentials'})

    def test_login_rate_limit_precedes_password_check(self):
        self.repo.allow_login.return_value = False
        response = self.client.post('/auth/token', json={'username': 'demo', 'password': self.password})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['retry-after'], '60')
        self.repo.get_by_username.assert_not_awaited()

    def test_public_endpoints(self):
        for path in ['/', '/health', '/docs', '/openapi.json']:
            self.assertEqual(self.client.get(path).status_code, 200)

    def test_secret_is_required(self):
        for secret in ['', 'short']:
            self.config.jwt_secret = secret
            with self.assertRaises(ValueError):
                self.config.validate_auth()
