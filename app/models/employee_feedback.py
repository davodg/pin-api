from datetime import datetime


class EmployeeFeedback(object):
    def __init__(self, feedback: dict):
        self.id = feedback.get('id')
        self.name = feedback.get('name')
        self.email = feedback.get('email')
        self.phone_number = feedback.get('phone_number')
        self.corporate_email = feedback.get('corporate_email')
        self.department = feedback.get('department')
        self.location = feedback.get('location')
        self.company_tenure = feedback.get('company_tenure')
        self.gender = feedback.get('gender')
        self.generation = feedback.get('generation')
        self.company_level_0 = feedback.get('l0_company')
        self.directorate_level_1 = feedback.get('l1_directorate')
        self.management_level_2 = feedback.get('l2_management')
        self.coordination_level_3 = feedback.get('l3_coordination')
        self.area_level_4 = feedback.get('l4_area')
        self.response_date = self._to_date(feedback.get('response_date'))
        self.interest_in_position = feedback.get('interest_in_position')
        self.interest_in_position_comments = feedback.get('interest_in_position_comments')
        self.contribution = feedback.get('contribution')
        self.contribution_comments = feedback.get('contribution_comments')
        self.learning_and_development = feedback.get('learning_and_development')
        self.learning_and_development_comments = feedback.get('learning_and_development_comments')
        self.feedback = feedback.get('feedback')
        self.feedback_comments = feedback.get('feedback_comments')
        self.manager_interaction = feedback.get('manager_interaction')
        self.manager_interaction_comments = feedback.get('manager_interaction_comments')
        self.opportunity_clarity = feedback.get('opportunity_clarity')
        self.opportunity_clarity_comments = feedback.get('opportunity_clarity_comments')
        self.permanence_expectation = feedback.get('permanence_expectation')
        self.permanence_expectation_comments = feedback.get('permanence_expectation_comments')
        self.enps = feedback.get('enps')
        self.enps_comments = feedback.get('enps_comments')

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone_number": self.phone_number,
            "corporate_email": self.corporate_email,
            "department": self.department,
            "location": self.location,
            "company_tenure": self.company_tenure,
            "gender": self.gender,
            "generation": self.generation,
            "l0_company": self.company_level_0,
            "l1_directorate": self.directorate_level_1,
            "l2_management": self.management_level_2,
            "l3_coordination": self.coordination_level_3,
            "l4_area": self.area_level_4,
            "response_date": self.response_date,
            "interest_in_position": self.interest_in_position,
            "interest_in_position_comments": self.interest_in_position_comments,
            "contribution": self.contribution,
            "contribution_comments": self.contribution_comments,
            "learning_and_development": self.learning_and_development,
            "learning_and_development_comments": self.learning_and_development_comments,
            "feedback": self.feedback,
            "feedback_comments": self.feedback_comments,
            "manager_interaction": self.manager_interaction,
            "manager_interaction_comments": self.manager_interaction_comments,
            "opportunity_clarity": self.opportunity_clarity,
            "opportunity_clarity_comments": self.opportunity_clarity_comments,
            "permanence_expectation": self.permanence_expectation,
            "permanence_expectation_comments": self.permanence_expectation_comments,
            "enps": self.enps,
            "enps_comments": self.enps_comments,
        }
    

    def _to_date(self, value):
        if not value:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            return datetime.strptime(value.strip(), "%d/%m/%Y").date()
        raise TypeError("Expected str or datetime")