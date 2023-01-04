from django.contrib import admin
from django.utils.html import format_html

from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.choices import BlueprintPage
from blueprint.constants import (
    BLUEPRINT_FORMULA,
    CHIP_DIV_END,
    TEAMS_AIRTABLE_NAME,
    TEAMS_REQUIRED_FIELDS,
)
from blueprint.models.team import TeamBlueprint


@admin.register(TeamBlueprint)
class TeamBlueprintAdmin(BlueprintAdmin):
    blueprint_page_name = str(BlueprintPage.TEAMS)
    airtable_tab_name = TEAMS_AIRTABLE_NAME
    blueprint_required_fields = TEAMS_REQUIRED_FIELDS
    blueprint_formula = BLUEPRINT_FORMULA
    blueprint_model = TeamBlueprint
    model_parameter_name = 'name'
    blueprint_parameter_name_value = 'Name'

    def formatted_charter(self, obj):
        return format_html(
            '<div style="'
            'min-width: 220px;'
            'padding: 12px;'
            'box-shadow: -1px 1px 5px #ddd, 1px 1px 5px #ddd;">'
            + obj.charter
            + CHIP_DIV_END
        )

    formatted_charter.short_description = 'Description'  # type: ignore

    list_display = (
        'name',
        'airtable_record_id',
        'updated_at',
    )

    fields = (
        'name',
        'description',
        'formatted_charter',
        'airtable_record_id',
        'updated_at',
    )

    def get_default_fields(self, fields: dict, _) -> dict:
        return {
            'description': fields.get('Description'),
            'charter': fields.get('Charter'),
        }
