from django.contrib import admin

from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.choices import BlueprintPage
from blueprint.constants import (
    ANSWER,
    QUESTION_TEXT,
    QUESTIONNAIRE,
    QUESTIONS_AIRTABLE_NAME,
    QUESTIONS_REQUIRED_FIELDS,
    SHORT_ANSWER,
    SHORT_ANSWER_OPTIONS,
)
from blueprint.models.question import QuestionBlueprint


@admin.register(QuestionBlueprint)
class QuestionBlueprintAdmin(BlueprintAdmin):
    blueprint_page_name = str(BlueprintPage.QUESTIONS)
    airtable_tab_name = QUESTIONS_AIRTABLE_NAME
    blueprint_required_fields = QUESTIONS_REQUIRED_FIELDS
    blueprint_model = QuestionBlueprint
    model_parameter_name = 'question_text'
    blueprint_parameter_name_value = QUESTION_TEXT

    list_display = (
        'question_text',
        'airtable_record_id',
        'created_at',
        'updated_at',
    )

    def get_default_fields(self, fields: dict, _) -> dict:
        return {
            'questionnaire': fields.get(QUESTIONNAIRE),
            'answer': fields.get(ANSWER),
            'short_answer': fields.get(SHORT_ANSWER),
            'short_answer_options': fields.get(SHORT_ANSWER_OPTIONS),
        }
