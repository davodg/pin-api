from typing import Optional, Dict, Any, List, Tuple
from math import ceil

from app.storage.postgres import Postgres
from app.models.employee_feedback import FeedbackCreate, FeedbackReplace, FeedbackUpdate, FeedbackResponse


class FeedbackNotFound(Exception):
    pass


class FeedbackRepository:
    def __init__(self, db: Postgres):
        self.db = db

    async def create(self, feedback: FeedbackCreate):
        data = feedback.model_dump()
        # Column names come exclusively from our validated model, never raw input.
        columns = ', '.join(data)
        placeholders = ', '.join(f'%({name})s' for name in data)
        rows = await self.db.execute(
            f'INSERT INTO employee_feedback ({columns}) VALUES ({placeholders}) '
            f'RETURNING {self._select_columns()}', data,
        )
        return self._write_response(rows)

    async def get(self, page: int, limit: int, filters: Optional[Dict[str, Any]] = None):
        filters = self._convert_filter_to_dict(filters)

        if filters.get("id"):
            sql = f"SELECT {self._select_columns()} FROM employee_feedback WHERE id = %s"
            rows = await self.db.query(sql, (str(filters["id"]),))
            cols = self._columns_for_employee_feedback()
            normalized = self._normalize(rows, cols)
            data = normalized[0] if normalized else None
            total = 1 if data else 0

            return {
                'data': data,
                'meta': {"page": 1, "limit": 1, "total": total, "pages": 1}
            }

        where_sql, params = self._build_where(filters)

        order_by = "response_date DESC NULLS LAST, id DESC"
        offset = (page - 1) * limit

        sql = f"""
            SELECT {self._select_columns()}
            FROM employee_feedback
            {where_sql}
            ORDER BY {order_by}
            LIMIT %s OFFSET %s
        """
        rows = await self.db.query(sql, params + [limit, offset])

        count_sql = f"SELECT COUNT(*) FROM employee_feedback {where_sql}"
        total_rows = await self.db.query(count_sql, params)
        total = int(total_rows[0][0]) if total_rows else 0
        pages = ceil(total / limit) if limit else 1

        cols = self._columns_for_employee_feedback()
        data = self._normalize(rows, cols)

        return {
            'data': data,
            'meta': {"page": page, "limit": limit, "total": total, "pages": pages}
        }


    async def delete(self, feedback_id):
        rows = await self.db.execute(
            'DELETE FROM employee_feedback WHERE id = %s RETURNING id;', (str(feedback_id),),
        )
        if not rows:
            raise FeedbackNotFound()
        return {'data': {'id': rows[0][0]}, 'meta': {}}

    async def update(self, feedback_id, feedback: FeedbackReplace):
        return await self._update_fields(feedback_id, feedback.model_dump())

    async def patch(self, feedback_id, feedback: FeedbackUpdate):
        return await self._update_fields(feedback_id, feedback.model_dump(exclude_unset=True))

    async def _update_fields(self, feedback_id, data):
        # Both callers supply Pydantic fields with extra='forbid'.
        assignments = ', '.join(f'{name} = %({name})s' for name in data)
        rows = await self.db.execute(
            f'UPDATE employee_feedback SET {assignments} WHERE id = %(id)s '
            f'RETURNING {self._select_columns()}', {**data, 'id': str(feedback_id)},
        )
        return self._write_response(rows)

    def _write_response(self, rows):
        if not rows:
            raise FeedbackNotFound()
        return {'data': self._normalize(rows, self._columns_for_employee_feedback())[0], 'meta': {}}

    def _convert_filter_to_dict(self, filters):
        if filters is None:
            return {}
        if isinstance(filters, dict):
            return {k: v for k, v in filters.items() if v is not None}
        if hasattr(filters, "model_dump"):
            return filters.model_dump(exclude_none=True)
        if hasattr(filters, "dict"):
            return filters.dict(exclude_none=True)
        return {}


    def _build_where(self, filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
        clauses: List[str] = []
        params: List[Any] = []

        string_cols = {
            "email": "email",
            "corporate_email": "corporate_email",
            "department": "department",
            "location": "location",
            "gender": "gender",
            "generation": "generation",
            "name": "name",
        }
        for key, col in string_cols.items():
            val = filters.get(key)
            if val:
                clauses.append(f"{col} ILIKE %s")
                params.append(f"%{val}%")

        if filters.get("response_date_from"):
            clauses.append("response_date >= %s")
            params.append(filters["response_date_from"])
        if filters.get("response_date_to"):
            clauses.append("response_date <= %s")
            params.append(filters["response_date_to"])

        ranges = {
            "enps": ("enps_min", "enps_max"),
            "interest_in_position": ("interest_in_position_min", "interest_in_position_max"),
            "contribution": ("contribution_min", "contribution_max"),
            "learning_and_development": ("learning_and_development_min", "learning_and_development_max"),
            "feedback": ("feedback_min", "feedback_max"),
            "manager_interaction": ("manager_interaction_min", "manager_interaction_max"),
            "opportunity_clarity": ("opportunity_clarity_min", "opportunity_clarity_max"),
            "permanence_expectation": ("permanence_expectation_min", "permanence_expectation_max"),
        }
        for col, (min_key, max_key) in ranges.items():
            min_val = filters.get(min_key)
            max_val = filters.get(max_key)
            if min_val is not None:
                clauses.append(f"{col} >= %s")
                params.append(min_val)
            if max_val is not None:
                clauses.append(f"{col} <= %s")
                params.append(max_val)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where_sql, params

    def _select_columns(self) -> str:
        return (
            "id, name, email, corporate_email, phone_number, department, location, "
            "company_tenure, gender, generation, "
            "l0_company, l1_directorate, l2_management, "
            "l3_coordination, l4_area, response_date, "
            "interest_in_position, interest_in_position_comments, "
            "contribution, contribution_comments, "
            "learning_and_development, learning_and_development_comments, "
            "feedback, feedback_comments, "
            "manager_interaction, manager_interaction_comments, "
            "opportunity_clarity, opportunity_clarity_comments, "
            "permanence_expectation, permanence_expectation_comments, "
            "enps, enps_comments"
        )

    def _columns_for_employee_feedback(self) -> List[str]:
        return [
            "id", "name", "email", "corporate_email", "phone_number", "department", "location",
            "company_tenure", "gender", "generation",
            "l0_company", "l1_directorate", "l2_management",
            "l3_coordination", "l4_area", "response_date",
            "interest_in_position", "interest_in_position_comments",
            "contribution", "contribution_comments",
            "learning_and_development", "learning_and_development_comments",
            "feedback", "feedback_comments",
            "manager_interaction", "manager_interaction_comments",
            "opportunity_clarity", "opportunity_clarity_comments",
            "permanence_expectation", "permanence_expectation_comments",
            "enps", "enps_comments",
        ]


    def _normalize(self, rows: List[tuple], columns: List[str]) -> List[FeedbackResponse]:
        return [FeedbackResponse.model_validate(dict(zip(columns, row))) for row in rows]
