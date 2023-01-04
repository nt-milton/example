import logging
from typing import Dict, Tuple

from blueprint.models.question import QuestionBlueprint
from library.models import LibraryEntry, Question, Questionnaire
from organization.models import Organization

logger = logging.getLogger(__name__)


def _get_or_create_questionnaire(
    questionnaire_name: str,
    questionnaires: Dict[str, Questionnaire],
    organization: Organization,
) -> Tuple[bool, Questionnaire]:
    questionnaire = questionnaires.get(questionnaire_name)
    existing_questionnaire = Questionnaire.objects.filter(
        name=questionnaire_name, organization=organization
    )

    if not questionnaire and existing_questionnaire.exists():
        return True, existing_questionnaire.first()

    if questionnaire is None:
        questionnaire = Questionnaire.objects.create(
            name=questionnaire_name, organization=organization
        )
    return False, questionnaire


def prescribe(organization: Organization) -> list[str]:
    status_detail: list[str] = []
    questionnaires: Dict[str, Questionnaire] = {}
    for question_blueprint in QuestionBlueprint.objects.order_by('id').iterator():
        try:
            exists, questionnaire = _get_or_create_questionnaire(
                questionnaire_name=question_blueprint.questionnaire,
                questionnaires=questionnaires,
                organization=organization,
            )
            if exists:
                logger.info(
                    f'Questionnaire already exists for organization: {organization}'
                )
                return status_detail
            questionnaires[question_blueprint.questionnaire] = questionnaire
            library_entry = LibraryEntry.objects.create(
                organization=organization,
                answer_text=question_blueprint.answer,
                short_answer_text=question_blueprint.short_answer,
            )
            question = Question.objects.create(
                library_entry=library_entry,
                text=question_blueprint.question_text,
                metadata={
                    "sheet": {"name": "Sheet1", "position": 0},
                    "answer": {"address": "Sheet1!B1", "options": []},
                    "shortAnswer": {
                        "address": "Sheet1!C1",
                        "options": ["Yes", "No", "N/A"],
                    },
                    "questionAddress": "Sheet1!C3",
                },
                default=True,
            )
            questionnaire.questions.add(question)

            logger.info(
                f'New question {question} created for organization: {organization}'
            )
        except Exception as e:
            error_message = f'Error prescribing {question_blueprint}: {e}'
            status_detail.append(error_message)
            logger.warning(error_message)
    return status_detail
