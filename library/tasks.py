from typing import List

from laika.celery import app as celery_app
from library.models import Question
from library.services.question import QuestionService
from user.models import User


@celery_app.task(name='Create Library Equivalent Suggestions')
def create_library_equivalent_suggestions(
    latest_id, question_ids: List[str], user_id: str, library_task_id: int
):
    user = User.objects.get(id=user_id)
    questions = Question.objects.filter(id__in=question_ids)
    QuestionService.create_suggestions_for_questions(
        latest_id, questions, user, library_task_id
    )
