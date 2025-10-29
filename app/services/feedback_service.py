from app.repositories.feedback_repository import FeedbackRepository

class FeedbackService(object):
    def __init__(self):
        self.repository = FeedbackRepository()

    def create(self, feedback):
        return self.repository.create(feedback)
    
    def get(self, page, limit, filters=None):
        return self.repository.get(page, limit, filters)

    def delete(self, feedback_id):
        return self.repository.delete(feedback_id)

    def update(self, feedback_id, feedback):
        return self.repository.update(feedback_id, feedback)