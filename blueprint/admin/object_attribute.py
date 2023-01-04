from django.contrib import admin
from django.utils.html import format_html

from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.choices import BlueprintPage
from blueprint.constants import (
    ANCHOR,
    ATTRIBUTE_TYPE,
    BLUEPRINT_FORMULA,
    CHIP_DIV_END,
    CHIP_DIV_START,
    DEFAULT_VALUE,
    DISPLAY_INDEX,
    IS_PROTECTED,
    IS_REQUIRED,
    MIN_WIDTH,
    NAME,
    OBJECT_ATTRIBUTE_REQUIRED_FIELDS,
    OBJECT_ATTRIBUTES_AIRTABLE_NAME,
    REFERENCE_ID,
    SELECT_OPTIONS,
    TYPE_NAME,
)
from blueprint.models.object import ObjectBlueprint
from blueprint.models.object_attribute import ObjectAttributeBlueprint


@admin.register(ObjectAttributeBlueprint)
class ObjectAttributeBlueprintAdmin(BlueprintAdmin):
    blueprint_page_name = str(BlueprintPage.OBJECT_ATTRIBUTES)
    airtable_tab_name = OBJECT_ATTRIBUTES_AIRTABLE_NAME
    blueprint_required_fields = OBJECT_ATTRIBUTE_REQUIRED_FIELDS
    blueprint_formula = BLUEPRINT_FORMULA
    blueprint_model = ObjectAttributeBlueprint
    model_parameter_name = 'reference_id'
    blueprint_parameter_name_value = REFERENCE_ID

    def formatted_object_type(self, obj):
        obj_type = ObjectBlueprint.objects.filter(
            type_name=obj.object_type_name
        ).first()

        if not obj_type:
            return '-'

        url = f'/admin/blueprint/objectblueprint/{obj_type.id}/change'
        return format_html(
            ANCHOR
            + url
            + '">'
            + CHIP_DIV_START.format(random_color='#d8d3dc')
            + obj.object_type_name
            + CHIP_DIV_END
            + '</a>'
        )

    formatted_object_type.short_description = 'Object Type Name'  # type: ignore
    formatted_object_type.admin_order_field = 'object_type_name'  # type: ignore

    official_fields = (
        'name',
        'formatted_object_type',
        'display_index',
        'attribute_type',
        'min_width',
        'default_value',
        'is_protected',
        'is_required',
        'select_options',
        'airtable_record_id',
        'updated_at',
    )

    list_display = official_fields
    fields = official_fields
    search_fields = (
        'name',
        'object_type_name',
    )

    def get_default_fields(self, fields: dict, _) -> dict:
        return {
            'name': fields.get(NAME),
            'object_type_name': fields.get(TYPE_NAME),
            'attribute_type': fields.get(ATTRIBUTE_TYPE),
            'min_width': fields.get(MIN_WIDTH),
            'display_index': fields.get(DISPLAY_INDEX),
            'is_protected': bool(fields.get(IS_PROTECTED)),
            'default_value': fields.get(DEFAULT_VALUE) or '',
            'select_options': fields.get(SELECT_OPTIONS) or '',
            'is_required': bool(fields.get(IS_REQUIRED)),
        }
