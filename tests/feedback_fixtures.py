from uuid import UUID

FEEDBACK_ID = UUID('d39033df-88af-4d46-a3a4-a56776e17a66')


def payload(**changes):
    return {
        'name': 'Demo', 'email': 'demo@example.com', 'corporate_email': 'demo@company.com',
        'department': 'Engineering', 'location': 'São Paulo', 'company_tenure': '1 year',
        'gender': 'Other', 'generation': 'Gen Y', 'interest_in_position': 7,
        'contribution': 7, 'learning_and_development': 7, 'feedback': 7,
        'manager_interaction': 7, 'opportunity_clarity': 7, 'permanence_expectation': 7,
        'enps': 8, **changes,
    }


def record(**changes):
    from app.models.employee_feedback import FeedbackResponse
    return FeedbackResponse(id=FEEDBACK_ID, **payload(**changes))


def row(repository, **changes):
    data = record(**changes).model_dump()
    return tuple(data[name] for name in repository._columns_for_employee_feedback())
