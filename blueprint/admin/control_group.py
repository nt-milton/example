from django.contrib import admin
from django.utils.html import format_html

from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.choices import BlueprintPage
from blueprint.constants import (
    ANCHOR,
    ANCHOR_END,
    CHIP_DIV_END,
    CHIP_DIV_START,
    GROUP_REQUIRED_FIELDS,
    GROUPS_AIRTABLE_NAME,
    NAME,
    REFERENCE_ID,
    SECTION_CHIP_DIV_START,
    SORT_ORDER,
    TL_SECTION_END,
    TL_SECTION_START,
)
from blueprint.models import ControlGroupBlueprint


@admin.register(ControlGroupBlueprint)
class ControlGroupBlueprintAdmin(BlueprintAdmin):
    blueprint_page_name = str(BlueprintPage.GROUPS)
    airtable_tab_name = GROUPS_AIRTABLE_NAME
    blueprint_required_fields = GROUP_REQUIRED_FIELDS

    blueprint_model = ControlGroupBlueprint
    model_parameter_name = 'reference_id'
    blueprint_parameter_name_value = REFERENCE_ID

    ordering = ('reference_id',)

    def formatted_reference_id(self, obj):
        url = f'/admin/blueprint/controlgroupblueprint/{obj.id}/change'
        return format_html(
            ANCHOR
            + url
            + '">'
            + CHIP_DIV_START.format(random_color='#d8d3dc')
            + obj.reference_id
            + CHIP_DIV_END
            + ANCHOR_END
        )

    formatted_reference_id.short_description = 'Reference ID'  # type: ignore
    formatted_reference_id.admin_order_field = 'reference_id'  # type: ignore

    def formatted_name(self, obj):
        return format_html('<div style="min-width: 250px;">' + obj.name + CHIP_DIV_END)

    formatted_name.short_description = 'Name'  # type: ignore
    formatted_name.admin_order_field = 'name'  # type: ignore

    def formatted_controls(self, obj):
        controls = []
        for control in obj.controls.iterator():
            div_start = SECTION_CHIP_DIV_START.format(random_color='#d8d3dc')
            url = f'/admin/blueprint/controlblueprint/{control.id}/change'
            controls.append(
                ANCHOR
                + url
                + '">'
                + div_start
                + control.reference_id
                + CHIP_DIV_END
                + ANCHOR_END
            )

        if not len(controls):
            return '-'
        return format_html(TL_SECTION_START + ''.join(controls) + TL_SECTION_END)

    formatted_controls.short_description = 'Controls'  # type: ignore

    official_fields = (
        'formatted_reference_id',
        'formatted_name',
        'formatted_controls',
        'airtable_record_id',
        'updated_at',
    )

    list_display = official_fields
    fields = official_fields

    def get_default_fields(self, fields: dict, _) -> dict:
        return {'name': fields.get(NAME), 'sort_order': fields.get(SORT_ORDER)}
