"""Create a local account: python -m app.create_user --username demo --role viewer."""
import argparse
import asyncio
from getpass import getpass
from uuid import uuid4

from psycopg.errors import UniqueViolation
from starlette.concurrency import run_in_threadpool

from app.repositories.user_repository import UserRepository
from app.security.auth import password_hasher
from app.storage.postgres import Postgres


async def create_user(username, role, password):
    password_hash = await run_in_threadpool(password_hasher.hash, password)
    db = Postgres()
    try:
        await db.open()
        await UserRepository(db).create(uuid4(), username, password_hash, role)
    finally:
        await db.close()


def main():
    parser = argparse.ArgumentParser(description='Create a pin-api user (no existing account is overwritten).')
    parser.add_argument('--username', required=True)
    parser.add_argument('--role', required=True, choices=['viewer', 'admin'])
    args = parser.parse_args()
    if not args.username.strip() or len(args.username) > 100:
        parser.error('Username must contain 1 to 100 characters and cannot be blank.')
    password = getpass('Password (12–128 characters): ')
    if not 12 <= len(password) <= 128:
        parser.error('Password must contain 12 to 128 characters.')
    if password != getpass('Confirm password: '):
        parser.error('Passwords do not match.')
    try:
        asyncio.run(create_user(args.username, args.role, password))
    except UniqueViolation:
        parser.exit(1, 'Username already exists.\n')
    print('User created.')


if __name__ == '__main__':
    main()
