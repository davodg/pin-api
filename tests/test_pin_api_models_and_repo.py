import datetime
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



from pydantic import ValidationError
from app.models.employee_feedback import FeedbackCreate, FeedbackReplace, FeedbackUpdate, FeedbackResponse
from app.models.feedback_filters import FeedbackFilters
from app.repositories.feedback_repository import FeedbackRepository, FeedbackNotFound
from tests.feedback_fixtures import FEEDBACK_ID, payload, row


class TestFeedbackModels(unittest.TestCase):
    def test_model_dump_preserves_date(self):
        model = FeedbackCreate(**payload(name='  Demo  ', response_date='2024-01-20'))
        self.assertEqual(model.name, 'Demo')
        self.assertEqual(model.model_dump()['response_date'], datetime.date(2024, 1, 20))
        self.assertEqual(model.model_dump(mode='json')['response_date'], '2024-01-20')

    def test_database_datetime_is_exposed_as_date(self):
        model = FeedbackResponse(id=FEEDBACK_ID, **payload(response_date=datetime.datetime(2024, 1, 20, 12)))
        self.assertEqual(model.response_date, datetime.date(2024, 1, 20))

    def test_all_required_fields_reject_omission_and_null(self):
        for name, field in FeedbackCreate.model_fields.items():
            if not field.is_required():
                continue
            data = payload()
            del data[name]
            with self.subTest(name=name):
                with self.assertRaises(ValidationError):
                    FeedbackCreate(**data)
                with self.assertRaises(ValidationError):
                    FeedbackUpdate(**{name: None})

    def test_patch_preserves_explicit_null_and_omission(self):
        self.assertEqual(FeedbackUpdate(feedback_comments=None).model_dump(exclude_unset=True), {'feedback_comments': None})
        self.assertEqual(FeedbackUpdate(enps=0).model_dump(exclude_unset=True), {'enps': 0})


class TestFeedbackRepository(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.repo = FeedbackRepository(mock.AsyncMock())

    def test_convert_filter_to_dict(self):
        self.assertEqual(self.repo._convert_filter_to_dict(None), {})
        filters = {'email': 'alice', 'name': None}
        self.assertEqual(self.repo._convert_filter_to_dict(filters), {'email': 'alice'})
        ff = FeedbackFilters(email='bob@example.com', generation=None)
        out = self.repo._convert_filter_to_dict(ff)
        self.assertEqual(out, {'email': 'bob@example.com'})
        class Dummy:
            def model_dump(self, exclude_none=True):
                return {'foo': 'bar'}
        dummy = Dummy()
        self.assertEqual(self.repo._convert_filter_to_dict(dummy), {'foo': 'bar'})

    def test_build_where_string_filters(self):
        filters = {'email': 'john', 'name': 'doe'}
        where_sql, params = self.repo._build_where(filters)
        self.assertIn('email ILIKE %s', where_sql)
        self.assertIn('name ILIKE %s', where_sql)
        self.assertEqual(params, ['%john%', '%doe%'])

    def test_build_where_range_filters(self):
        filters = {'enps_min': 5, 'enps_max': 10}
        where_sql, params = self.repo._build_where(filters)
        self.assertIn('enps >= %s', where_sql)
        self.assertIn('enps <= %s', where_sql)
        self.assertEqual(params, [5, 10])

    def test_build_where_date_filters(self):
        date_from = datetime.date(2024, 1, 1)
        date_to = datetime.date(2024, 12, 31)
        filters = {'response_date_from': date_from, 'response_date_to': date_to}
        where_sql, params = self.repo._build_where(filters)
        self.assertIn('response_date >= %s', where_sql)
        self.assertIn('response_date <= %s', where_sql)
        self.assertEqual(params, [date_from, date_to])

    def test_normalize(self):
        models = self.repo._normalize([row(self.repo, phone_number='11999999999')], self.repo._columns_for_employee_feedback())
        self.assertEqual(models[0].id, FEEDBACK_ID)
        self.assertEqual(models[0].phone_number, '11999999999')

    async def test_create(self):
        self.repo.db.execute.return_value = [row(self.repo)]
        result = await self.repo.create(FeedbackCreate(**payload()))
        self.assertEqual(result['data'].id, FEEDBACK_ID)
        params = self.repo.db.execute.await_args.args[1]
        self.assertEqual(params['name'], 'Demo')
        self.assertNotIn('id', params)

    async def test_get_by_id(self):
        fake_row = (1, 'Bob', 'bob@example.com', None, None, None, None, None, None,
                    None, None, None, None, None, None,
                    None, None, None, None, None, None, None, None, None, None,
                    None, None, None, None, None, None)
        self.repo.db.query.return_value = [fake_row]
        with mock.patch.object(self.repo, '_normalize', return_value=[{'id': 1, 'name': 'Bob'}]):
            ctx = await self.repo.get(page=1, limit=10, filters={'id': 1})
            self.repo.db.query.assert_awaited_once()
            self.assertEqual(ctx['data']['id'], 1)
            self.assertEqual(ctx['meta']['total'], 1)

    async def test_get_with_filters_and_pagination(self):
        def side_effect_query(sql, params):
            if 'COUNT' in sql:
                return [(7,)]
            else:
                return [('row',)]
        self.repo.db.query.side_effect = side_effect_query
        with mock.patch.object(self.repo, '_normalize', return_value=[{'id': 1}, {'id': 2}]):
            ctx = await self.repo.get(page=2, limit=3, filters={})
            self.assertEqual(self.repo.db.query.await_count, 2)
            self.assertEqual(ctx['data'], [{'id': 1}, {'id': 2}])
            self.assertEqual(ctx['meta']['page'], 2)
            self.assertEqual(ctx['meta']['limit'], 3)
            self.assertEqual(ctx['meta']['total'], 7)
            self.assertEqual(ctx['meta']['pages'], 3)

    async def test_update_replaces_nullable_fields(self):
        self.repo.db.execute.return_value = [row(self.repo)]
        await self.repo.update(FEEDBACK_ID, FeedbackReplace(**payload()))
        params = self.repo.db.execute.await_args.args[1]
        self.assertIn('feedback_comments', params)
        self.assertIsNone(params['feedback_comments'])
        self.assertEqual(params['id'], str(FEEDBACK_ID))

    async def test_patch_updates_only_supplied_columns(self):
        self.repo.db.execute.return_value = [row(self.repo)]
        await self.repo.patch(FEEDBACK_ID, FeedbackUpdate(feedback_comments=None))
        query, params = self.repo.db.execute.await_args.args
        self.assertEqual(params, {'feedback_comments': None, 'id': str(FEEDBACK_ID)})
        self.assertIn('SET feedback_comments = %(feedback_comments)s WHERE', query)

    async def test_missing_write_target(self):
        self.repo.db.execute.return_value = []
        for call in [lambda: self.repo.update(FEEDBACK_ID, FeedbackReplace(**payload())),
                     lambda: self.repo.patch(FEEDBACK_ID, FeedbackUpdate(name='Changed')),
                     lambda: self.repo.delete(FEEDBACK_ID)]:
            with self.assertRaises(FeedbackNotFound):
                await call()

    async def test_delete(self):
        self.repo.db.execute.return_value = [(str(FEEDBACK_ID),)]
        result = await self.repo.delete(FEEDBACK_ID)
        self.assertEqual(result['data']['id'], str(FEEDBACK_ID))
        self.repo.db.execute.assert_awaited_once_with(
            'DELETE FROM employee_feedback WHERE id = %s RETURNING id;', (str(FEEDBACK_ID),))
