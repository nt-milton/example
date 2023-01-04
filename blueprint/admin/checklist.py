from django.contrib import admin

from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.choices import BlueprintPage
from blueprint.constants import (
    BLUEPRINT_FORMULA,
    CHECKLIST_AIRTABLE_NAME,
    CHECKLIST_REQUIRED_FIELDS,
)
from blueprint.models.checklist import ChecklistBlueprint


@admin.register(ChecklistBlueprint)
class ChecklistBlueprintAdmin(BlueprintAdmin):
    blueprint_page_name = str(BlueprintPage.CHECKLIST)
    airtable_tab_name = CHECKLIST_AIRTABLE_NAME
    blueprint_required_fields = CHECKLIST_REQUIRED_FIELDS
    blueprint_formula = BLUEPRINT_FORMULA
    blueprint_model = ChecklistBlueprint
    model_parameter_name = 'reference_id'
    blueprint_parameter_name_value = 'Reference ID'

    list_display = (
        'description',
        'airtable_record_id',
        'created_at',
        'updated_at',
    )

    def get_default_fields(self, fields: dict, _) -> dict:
        return {
            'checklist': fields.get('Checklist'),
            'description': fields.get('Description'),
            'type': fields.get('Type'),
            'category': fields.get('Category'),
        }
