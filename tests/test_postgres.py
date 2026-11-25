import asyncio
import unittest
from unittest import mock

from app.storage.postgres import Postgres
import main


class TestPostgres(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db = Postgres()
        self.pool = mock.MagicMock()
        self.db.pool = self.pool
        self.connection_context = self.pool.connection.return_value
        self.conn = self.connection_context.__aenter__.return_value
        self.cur = mock.AsyncMock()
        self.conn.cursor = mock.MagicMock()
        self.conn.cursor.return_value.__aenter__.return_value = self.cur

    async def test_query_fetches_and_releases_connection(self):
        self.cur.fetchall.return_value = [(1,)]
        self.assertEqual(await self.db.query('SELECT %s', (1,)), [(1,)])
        self.cur.execute.assert_awaited_once_with('SELECT %s', (1,))
        self.cur.fetchall.assert_awaited_once()
        self.connection_context.__aexit__.assert_awaited_once_with(None, None, None)

    async def test_execute_returning(self):
        self.cur.description = [('id',)]
        self.cur.fetchall.return_value = [(42,)]
        self.assertEqual(await self.db.execute('INSERT ... RETURNING id', {}), [(42,)])
        self.cur.execute.assert_awaited_once_with('INSERT ... RETURNING id', {})

    async def test_execute_without_rows(self):
        self.cur.description = None
        self.assertIsNone(await self.db.execute('DELETE ...', (1,)))
        self.cur.fetchall.assert_not_awaited()

    async def test_error_reaches_connection_context_for_rollback(self):
        error = RuntimeError('query failed')
        self.cur.execute.side_effect = error
        with self.assertRaisesRegex(RuntimeError, 'query failed'):
            await self.db.execute('invalid')
        args = self.connection_context.__aexit__.await_args.args
        self.assertIs(args[0], RuntimeError)
        self.assertIs(args[1], error)

    async def test_query_yields_to_event_loop(self):
        started = asyncio.Event()
        release = asyncio.Event()

        async def execute(*args):
            started.set()
            await release.wait()

        self.cur.execute.side_effect = execute
        task = asyncio.create_task(self.db.query('SELECT 1'))
        try:
            await asyncio.wait_for(started.wait(), timeout=1)
            self.assertFalse(task.done())
        finally:
            release.set()
            await task


class TestLifespan(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        patcher = mock.patch.dict('os.environ', {'JWT_SECRET': 'test-only-secret-' * 3})
        patcher.start()
        self.addCleanup(patcher.stop)

    async def test_pool_is_opened_and_closed(self):
        db = mock.AsyncMock()
        with mock.patch.object(main, 'Postgres', return_value=db):
            async with main.lifespan(main.app):
                db.open.assert_awaited_once()
                self.assertIs(main.app.state.feedback_service.repository.db, db)
                db.close.assert_not_awaited()
            db.close.assert_awaited_once()

    async def test_pool_is_closed_on_startup_failure(self):
        db = mock.AsyncMock()
        db.open.side_effect = RuntimeError('unavailable')
        with mock.patch.object(main, 'Postgres', return_value=db):
            with self.assertRaisesRegex(RuntimeError, 'unavailable'):
                async with main.lifespan(main.app):
                    self.fail('startup should fail')
            db.close.assert_awaited_once()

    async def test_pool_is_closed_on_application_failure(self):
        db = mock.AsyncMock()
        with mock.patch.object(main, 'Postgres', return_value=db):
            with self.assertRaisesRegex(RuntimeError, 'application failed'):
                async with main.lifespan(main.app):
                    raise RuntimeError('application failed')
            db.close.assert_awaited_once()
