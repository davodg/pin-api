from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from app.config import Config

password_hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)


def unauthorized():
    return HTTPException(401, 'Invalid credentials', headers={'WWW-Authenticate': 'Bearer'})


def verify_password(password, password_hash):
    try:
        return password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


class AuthService:
    def __init__(self, repository, config: Config, dummy_hash: str):
        self.repository = repository
        self.config = config
        self.dummy_hash = dummy_hash

    def issue_token(self, user_id):
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {'sub': str(user_id), 'iat': now, 'exp': now + timedelta(minutes=15),
             'iss': self.config.jwt_issuer, 'aud': self.config.jwt_audience},
            self.config.jwt_secret, algorithm='HS256',
        )

    async def authenticate(self, username, password):
        user = await self.repository.get_by_username(username)
        valid = await run_in_threadpool(
            verify_password, password, user['password_hash'] if user else self.dummy_hash,
        )
        if not valid or not user or not user['is_active']:
            raise unauthorized()
        return {'access_token': self.issue_token(user['id']), 'token_type': 'bearer', 'expires_in': 900}

    async def current_user(self, token):
        try:
            payload = jwt.decode(
                token, self.config.jwt_secret, algorithms=['HS256'],
                issuer=self.config.jwt_issuer, audience=self.config.jwt_audience,
                options={'require': ['sub', 'iat', 'exp', 'iss', 'aud']},
            )
            user_id = str(UUID(payload['sub']))
        except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
            raise unauthorized()
        user = await self.repository.get_by_id(user_id)
        if not user or not user['is_active']:
            raise unauthorized()
        return user


async def get_auth_service(request: Request):
    return request.app.state.auth_service


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    service: AuthService = Depends(get_auth_service),
):
    if credentials is None:
        raise unauthorized()
    return await service.current_user(credentials.credentials)


def require_role(*roles):
    async def check(user=Depends(get_current_user)):
        if user['role'] not in roles:
            raise HTTPException(403, 'Insufficient permissions')
        return user
    return check


async def limit_login(request: Request, service: AuthService = Depends(get_auth_service)):
    address = request.client.host if request.client else 'unknown'
    if not await service.repository.allow_login(address):
        raise HTTPException(429, 'Too many login attempts', headers={'Retry-After': '60'})
