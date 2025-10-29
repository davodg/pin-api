from typing import Optional, Dict, Any, List, Tuple
from math import ceil
from app.config import Config
from app.storage.postgres import Postgres
from app.models.employee_feedback import EmployeeFeedback


class FeedbackRepository(object):
    def __init__(self):
        self.config = Config()
        self.db = Postgres()
        self.context = {'data': {}, 'meta': {}}

    def create(self, feedback):
        data = self._check_model(feedback).to_dict()
        query = """
            INSERT INTO employee_feedback (
                name, email, corporate_email, department, location,
                company_tenure, gender, generation,
                l0_company, l1_directorate, l2_management,
                l3_coordination, l4_area, response_date,
                interest_in_position, interest_in_position_comments,
                contribution, contribution_comments,
                learning_and_development, learning_and_development_comments,
                feedback, feedback_comments,
                manager_interaction, manager_interaction_comments,
                opportunity_clarity, opportunity_clarity_comments,
                permanence_expectation, permanence_expectation_comments,
                enps, enps_comments
            ) VALUES (
                %(name)s, %(email)s, %(corporate_email)s, %(department)s, %(location)s,
                %(company_tenure)s, %(gender)s, %(generation)s,
                %(l0_company)s, %(l1_directorate)s, %(l2_management)s,
                %(l3_coordination)s, %(l4_area)s, %(response_date)s,
                %(interest_in_position)s, %(interest_in_position_comments)s,
                %(contribution)s, %(contribution_comments)s,
                %(learning_and_development)s, %(learning_and_development_comments)s,
                %(feedback)s, %(feedback_comments)s,
                %(manager_interaction)s, %(manager_interaction_comments)s,
                %(opportunity_clarity)s, %(opportunity_clarity_comments)s,
                %(permanence_expectation)s, %(permanence_expectation_comments)s,
                %(enps)s, %(enps_comments)s
            )
            RETURNING id;
        """
        result = self.db.execute(query, data)
        data['id'] = result[0][0]
        self.context['data'] = data
        return self.context

    def get(self, page: int, limit: int, filters: Optional[Dict[str, Any]] = None):
        filters = self._convert_filter_to_dict(filters)
        page = max(1, int(page))
        limit = max(1, int(limit))

        if filters.get("id"):
            sql = f"SELECT {self._select_columns()} FROM employee_feedback WHERE id = %s"
            rows = self.db.query(sql, (filters["id"],))
            cols = self._columns_for_employee_feedback()
            normalized = self._normalize(rows, cols)
            data = normalized[0] if normalized else None
            total = 1 if data else 0
            self.context['data'] = data
            self.context['meta'] = {"page": 1, "limit": 1, "total": total, "pages": 1}
            return self.context

        where_sql, params = self._build_where(filters)

        order_by = "response_date DESC NULLS LAST"
        offset = (page - 1) * limit

        sql = f"""
            SELECT {self._select_columns()}
            FROM employee_feedback
            {where_sql}
            ORDER BY {order_by}
            LIMIT %s OFFSET %s
        """
        rows = self.db.query(sql, params + [limit, offset])

        count_sql = f"SELECT COUNT(*) FROM employee_feedback {where_sql}"
        total_rows = self.db.query(count_sql, params)
        total = int(total_rows[0][0]) if total_rows else 0
        pages = ceil(total / limit) if limit else 1

        cols = self._columns_for_employee_feedback()
        data = self._normalize(rows, cols)

        self.context['data'] = data
        self.context['meta'] = {"page": page, "limit": limit, "total": total, "pages": pages}
        return self.context

    def delete(self, feedback_id):
        query = "DELETE FROM employee_feedback WHERE id = %s;"
        self.db.execute(query, (feedback_id,))
        self.context['data'] = {'id': feedback_id}
        return self.context

    def update(self, feedback_id, feedback):
        data = self._check_model(feedback).to_dict()
        data['id'] = feedback_id
        query = """
            UPDATE employee_feedback SET
                name = %(name)s,
                email = %(email)s,
                corporate_email = %(corporate_email)s,
                department = %(department)s,
                location = %(location)s,
                company_tenure = %(company_tenure)s,
                gender = %(gender)s,
                generation = %(generation)s,
                l0_company = %(l0_company)s,
                l1_directorate = %(l1_directorate)s,
                l2_management = %(l2_management)s,
                l3_coordination = %(l3_coordination)s,
                l4_area = %(l4_area)s,
                response_date = %(response_date)s,
                interest_in_position = %(interest_in_position)s,
                interest_in_position_comments = %(interest_in_position_comments)s,
                contribution = %(contribution)s,
                contribution_comments = %(contribution_comments)s,
                learning_and_development = %(learning_and_development)s,
                learning_and_development_comments = %(learning_and_development_comments)s,
                feedback = %(feedback)s,
                feedback_comments = %(feedback_comments)s,
                manager_interaction = %(manager_interaction)s,
                manager_interaction_comments = %(manager_interaction_comments)s,
                opportunity_clarity = %(opportunity_clarity)s,
                opportunity_clarity_comments = %(opportunity_clarity_comments)s,
                permanence_expectation = %(permanence_expectation)s,
                enps = %(enps)s,
                enps_comments = %(enps_comments)s
            WHERE id = %(id)s;
        """
        self.db.execute(query, data)
        self.context['data'] = data
        return self.context
    
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
            "id, name, email, corporate_email, department, location, "
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
            "id", "name", "email", "corporate_email", "department", "location",
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


    def _normalize(self, rows: List[tuple], columns: List[str]) -> List[Dict[str, Any]]:
        results = []
        if not rows:
            return results

        for row in rows:
            data = {}
            for idx in range(len(columns)):
                col = columns[idx]
                data[col] = row[idx]
            model = EmployeeFeedback(data)
            results.append(model.to_dict())

        return results

    def _check_model(self, feedback):
        if isinstance(feedback, EmployeeFeedback):
            return feedback
        elif isinstance(feedback, dict):
            model = EmployeeFeedback(feedback)
            return model
        else:
            raise ValueError("Invalid feedback model")
