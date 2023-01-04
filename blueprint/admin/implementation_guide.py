import markdown
from django.contrib import admin
from django.utils.html import format_html

from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.choices import BlueprintPage
from blueprint.constants import (
    ANCHOR,
    ANCHOR_END,
    BLUEPRINT_FORMULA,
    CHIP_DIV_END,
    CHIP_DIV_START,
    DESCRIPTION,
    GUIDES_AIRTABLE_NAME,
    GUIDES_REQUIRED_FIELDS,
    NAME,
)
from blueprint.models.implementation_guide import ImplementationGuideBlueprint


@admin.register(ImplementationGuideBlueprint)
class ImplementationGuideBlueprintAdmin(BlueprintAdmin):
    blueprint_page_name = str(BlueprintPage.GUIDES)
    airtable_tab_name = GUIDES_AIRTABLE_NAME
    blueprint_required_fields = GUIDES_REQUIRED_FIELDS
    blueprint_formula = BLUEPRINT_FORMULA
    blueprint_model = ImplementationGuideBlueprint
    model_parameter_name = 'name'
    blueprint_parameter_name_value = NAME

    def formatted_name(self, obj):
        url = f'/admin/blueprint/implementationguideblueprint/{obj.id}/change'
        return format_html(
            ANCHOR
            + url
            + '">'
            + CHIP_DIV_START.format(random_color='#d8d3dc')
            + obj.name
            + CHIP_DIV_END
            + ANCHOR_END
        )

    formatted_name.short_description = 'Name'  # type: ignore
    formatted_name.admin_order_field = 'name'  # type: ignore

    official_fields = (
        'formatted_name',
        'airtable_record_id',
        'updated_at',
    )

    list_display = official_fields
    fields = (
        'formatted_name',
        'formatted_description',
        'airtable_record_id',
        'updated_at',
    )

    def formatted_description(self, obj):
        return format_html(
            '<div style="'
            'min-width: 220px;'
            'padding: 12px;'
            'box-shadow: -1px 1px 5px #ddd, 1px 1px 5px #ddd;">'
            + obj.description
            + CHIP_DIV_END
        )

    formatted_description.short_description = 'Description'  # type: ignore

    def get_default_fields(self, fields: dict, _) -> dict:
        formatted_description = markdown.markdown(str(fields.get(DESCRIPTION)))
        return {'description': formatted_description}
