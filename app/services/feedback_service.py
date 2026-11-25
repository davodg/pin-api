from app.repositories.feedback_repository import FeedbackRepository

class FeedbackService(object):
    def __init__(self, repository: FeedbackRepository):
        self.repository = repository

    async def create(self, feedback):
        return await self.repository.create(feedback)
    
    async def get(self, page, limit, filters=None):
        return await self.repository.get(page, limit, filters)

    async def delete(self, feedback_id):
        return await self.repository.delete(feedback_id)

    async def update(self, feedback_id, feedback):
        return await self.repository.update(feedback_id, feedback)
