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
    COLOR,
    DESCRIPTION,
    DISPLAY_INDEX,
    ICON,
    IS_SYSTEM_TYPE,
    OBJECT_AIRTABLE_NAME,
    OBJECT_COLORS,
    OBJECT_REQUIRED_FIELDS,
    RECT_DIV_START,
    SECTION_CHIP_DIV_START,
    TL_SECTION_END,
    TL_SECTION_START,
    TYPE,
)
from blueprint.models.object import ObjectBlueprint
from blueprint.models.object_attribute import ObjectAttributeBlueprint


@admin.register(ObjectBlueprint)
class ObjectBlueprintAdmin(BlueprintAdmin):
    blueprint_page_name = str(BlueprintPage.OBJECT)
    airtable_tab_name = OBJECT_AIRTABLE_NAME
    blueprint_required_fields = OBJECT_REQUIRED_FIELDS
    blueprint_formula = BLUEPRINT_FORMULA
    blueprint_model = ObjectBlueprint
    model_parameter_name = 'display_name'
    blueprint_parameter_name_value = 'Name'

    ordering = ('id',)

    def formatted_name(self, obj):
        url = f'/admin/blueprint/objectblueprint/{obj.id}/change'
        return format_html(
            ANCHOR
            + url
            + '">'
            + RECT_DIV_START.format(random_color='#d8d3dc')
            + obj.display_name
            + CHIP_DIV_END
            + ANCHOR_END
        )

    formatted_name.short_description = 'Name'  # type: ignore
    formatted_name.admin_order_field = 'name'  # type: ignore

    def formatted_color(self, obj):
        return format_html(
            CHIP_DIV_START.format(
                random_color=OBJECT_COLORS.get(obj.color, '#ffffff')
            ).replace('#222', '#fff')
            + obj.color
            + CHIP_DIV_END
        )

    formatted_color.short_description = 'Color'  # type: ignore
    formatted_color.admin_order_field = 'color'  # type: ignore

    def formatted_attrs(self, obj):
        attributes = []
        for attr in ObjectAttributeBlueprint.objects.filter(
            object_type_name=obj.type_name
        ):
            div_start = SECTION_CHIP_DIV_START.format(random_color='#d8d3dc')

            url = f'/admin/blueprint/objectattributeblueprint/{attr.id}/change'

            attributes.append(
                ANCHOR + url + '">' + div_start + attr.name + CHIP_DIV_END + ANCHOR_END
            )
        if not len(attributes):
            return '-'
        return format_html(TL_SECTION_START + ''.join(attributes) + TL_SECTION_END)

    formatted_attrs.short_description = 'Attributes'  # type: ignore

    official_fields = (
        'id',
        'formatted_name',
        'formatted_color',
        'type_name',
        'icon_name',
        'formatted_attrs',
        'display_index',
        'is_system_type',
        'description',
        'airtable_record_id',
        'updated_at',
    )

    list_display = official_fields
    fields = official_fields

    def get_default_fields(self, fields: dict, _) -> dict:
        return {
            'type_name': fields.get(TYPE),
            'color': fields.get(COLOR),
            'icon_name': fields.get(ICON),
            'display_index': fields.get(DISPLAY_INDEX),
            'is_system_type': bool(fields.get(IS_SYSTEM_TYPE)),
            'description': fields.get(DESCRIPTION),
        }
