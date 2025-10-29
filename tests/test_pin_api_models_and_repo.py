import datetime
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

from app.models.employee_feedback import EmployeeFeedback as APIEmployeeFeedback  
from app.models.feedback_filters import FeedbackFilters  
from app.repositories.feedback_repository import FeedbackRepository  


class TestPinApiEmployeeFeedback(unittest.TestCase):

    def test_to_dict_and_date_parsing(self):
        raw = {
            'id': '1',
            'name': 'Charlie',
            'email': 'charlie@example.com',
            'l0_company': 'Root',
            'l1_directorate': 'Dir',
            'l2_management': 'Mgr',
            'l3_coordination': 'Coord',
            'l4_area': 'Area',
            'response_date': '01/10/2024',
            'enps': 9
        }
        fb = APIEmployeeFeedback(raw)
        result = fb.to_dict()
        self.assertIsInstance(result['response_date'], datetime.date)
        self.assertEqual(result['response_date'], datetime.date(2024, 10, 1))
        self.assertEqual(result['l0_company'], 'Root')
        fb2 = APIEmployeeFeedback({'name': 'NoDate'})
        self.assertIsNone(fb2.to_dict()['response_date'])

    def test_invalid_date_type(self):
        with self.assertRaises(TypeError):
            APIEmployeeFeedback({'response_date': 123})


class TestFeedbackRepository(unittest.TestCase):

    def setUp(self):
        self.repo = FeedbackRepository()
        self.repo.db = mock.MagicMock()

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
        cols = self.repo._columns_for_employee_feedback()
        raw_row = [1, 'Eve', 'eve@example.com', 'eve@corp.com', 'IT', 'NY', '1', 'F', 'GenZ',
                   'L0', 'L1', 'L2', 'L3', 'L4', '01/01/2024',
                   4, 'ok', 3, 'ok', 5, 'ok', 2, 'meh', 3, 'meh', 4, 'meh', 5, 'meh', 10, 'meh']
        rows = [tuple(raw_row)]
        normalized = self.repo._normalize(rows, cols)
        self.assertEqual(len(normalized), 1)
        data = normalized[0]
        self.assertEqual(data['id'], 1)
        self.assertEqual(data['name'], 'Eve')
        self.assertEqual(data['email'], 'eve@example.com')
        self.assertIsInstance(data['response_date'], datetime.date)

    def test_check_model(self):
        model = self.repo._check_model({'name': 'Foo'})
        from app.models.employee_feedback import EmployeeFeedback as EF  
        self.assertIsInstance(model, EF)
        model2 = self.repo._check_model(model)
        self.assertIs(model2, model)
        with self.assertRaises(ValueError):
            self.repo._check_model(['invalid'])

    def test_create(self):
        self.repo.db.execute.return_value = [(42,)]
        feedback = {'name': 'Foo'}
        ctx = self.repo.create(feedback)
        self.repo.db.execute.assert_called_once()
        self.assertEqual(ctx['data']['id'], 42)
        self.assertEqual(ctx['data']['name'], 'Foo')

    def test_get_by_id(self):
        fake_row = (1, 'Bob', 'bob@example.com', None, None, None, None, None, None,
                    None, None, None, None, None, None,
                    None, None, None, None, None, None, None, None, None, None,
                    None, None, None, None, None, None)
        self.repo.db.query.return_value = [fake_row]
        with mock.patch.object(self.repo, '_normalize', return_value=[{'id': 1, 'name': 'Bob'}]):
            ctx = self.repo.get(page=1, limit=10, filters={'id': 1})
            self.repo.db.query.assert_called_once()
            self.assertEqual(ctx['data']['id'], 1)
            self.assertEqual(ctx['meta']['total'], 1)

    def test_get_with_filters_and_pagination(self):
        def side_effect_query(sql, params):
            if 'COUNT' in sql:
                return [(7,)]
            else:
                return [('row',)]
        self.repo.db.query.side_effect = side_effect_query
        with mock.patch.object(self.repo, '_normalize', return_value=[{'id': 1}, {'id': 2}]):
            ctx = self.repo.get(page=2, limit=3, filters={})
            self.assertEqual(self.repo.db.query.call_count, 2)
            self.assertEqual(ctx['data'], [{'id': 1}, {'id': 2}])
            self.assertEqual(ctx['meta']['page'], 2)
            self.assertEqual(ctx['meta']['limit'], 3)
            self.assertEqual(ctx['meta']['total'], 7)
            self.assertEqual(ctx['meta']['pages'], 3)

    def test_update(self):
        self.repo.db.execute.return_value = None
        data = {'name': 'Updated'}
        ctx = self.repo.update(5, data)
        self.repo.db.execute.assert_called_once()
        self.assertEqual(ctx['data']['id'], 5)
        self.assertEqual(ctx['data']['name'], 'Updated')

    def test_delete(self):
        self.repo.db.execute.return_value = None
        ctx = self.repo.delete(7)
        self.repo.db.execute.assert_called_once_with('DELETE FROM employee_feedback WHERE id = %s;', (7,))
        self.assertEqual(ctx['data']['id'], 7)