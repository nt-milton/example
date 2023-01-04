from django.contrib import admin
from django.utils.html import format_html

from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.choices import BlueprintPage
from blueprint.constants import (
    NAME,
    TRAINING_AIRTABLE_NAME,
    TRAINING_BLUEPRINT_FORMULA,
    TRAINING_REQUIRED_FIELDS,
)
from blueprint.helpers import get_attachment
from blueprint.models.training import TrainingBlueprint


@admin.register(TrainingBlueprint)
class TrainingBlueprintAdmin(BlueprintAdmin):
    blueprint_page_name = str(BlueprintPage.TRAINING)
    airtable_tab_name = TRAINING_AIRTABLE_NAME
    blueprint_required_fields = TRAINING_REQUIRED_FIELDS
    blueprint_formula = TRAINING_BLUEPRINT_FORMULA
    blueprint_model = TrainingBlueprint
    model_parameter_name = 'name'
    blueprint_parameter_name_value = NAME

    def preview(self, obj):
        print()
        view = f'<iframe src="{obj.file_attachment.url}" width="100%" height="700px" />'

        return format_html(view)

    preview.short_description = 'Training Preview'  # type: ignore

    list_display = (
        'name',
        'category',
        'created_at',
        'updated_at',
    )

    readonly_fields = [
        'preview',
    ]

    def get_default_fields(self, fields: dict, _) -> dict:
        return {
            'category': fields.get('Category'),
            'description': fields.get('Description'),
        }

    def execute_after_update_or_create(self, fields: dict, training):
        training.file_attachment = get_attachment(fields.get('File Attachment') or [])
        training.save()
        return True
