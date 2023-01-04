from alert.constants import ALERT_TYPES
from library.models import Questionnaire, QuestionnaireAlert
from user.models import User


def get_questionnaire_by_id(*, organization_id: str, questionnaire_id: int):
    return Questionnaire.objects.get(
        id=questionnaire_id, organization_id=organization_id
    )


class QuestionnaireService:
    @staticmethod
    def generate_alert_for_user_assigned(
        *,
        organization_id: str,
        questionnaire_id: int,
        created_by: User,
        user_assigned: User
    ):
        questionnaire = get_questionnaire_by_id(
            organization_id=organization_id, questionnaire_id=questionnaire_id
        )
        if user_assigned:
            QuestionnaireAlert.objects.custom_create(
                questionnaire=questionnaire,
                sender=created_by,
                receiver=user_assigned,
                alert_type=ALERT_TYPES['QUESTION_ASSIGNMENT'],
            )

    @staticmethod
    def delete_questionnaire_alerts(*, questionnaire: Questionnaire):
        questionnaire_alerts = QuestionnaireAlert.objects.filter(
            questionnaire=questionnaire
        )
        for questionnaire_alert in questionnaire_alerts:
            questionnaire_alert.alert.delete()
            questionnaire_alert.delete()
