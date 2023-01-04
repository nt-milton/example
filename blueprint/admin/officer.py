from django.contrib import admin

from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.choices import BlueprintPage
from blueprint.constants import (
    BLUEPRINT_FORMULA,
    OFFICERS_AIRTABLE_NAME,
    OFFICERS_REQUIRED_FIELDS,
)
from blueprint.models.officer import OfficerBlueprint


@admin.register(OfficerBlueprint)
class OfficerBlueprintAdmin(BlueprintAdmin):
    blueprint_page_name = str(BlueprintPage.OFFICERS)
    airtable_tab_name = OFFICERS_AIRTABLE_NAME
    blueprint_required_fields = OFFICERS_REQUIRED_FIELDS
    blueprint_formula = BLUEPRINT_FORMULA

    blueprint_model = OfficerBlueprint
    model_parameter_name = 'name'
    blueprint_parameter_name_value = 'Name'

    list_display = (
        'name',
        'airtable_record_id',
        'created_at',
        'updated_at',
    )

    def get_default_fields(self, fields: dict, _) -> dict:
        return {
            'description': fields.get('Description'),
        }
