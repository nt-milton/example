from typing import Dict, Optional

import markdown
from django.contrib import admin
from django.db.models import Q
from django.utils.html import format_html

from action_item.models import ActionItemFrequency
from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.admin.shared import get_roles_records
from blueprint.choices import BlueprintPage, SuggestedOwner
from blueprint.commons import logger
from blueprint.constants import (
    ACTION_ITEM_REQUIRED_FIELDS,
    ACTION_ITEMS_AIRTABLE_NAME,
    ANCHOR,
    ANCHOR_END,
    BLUEPRINT_FORMULA,
    CHIP_DIV_END,
    CHIP_DIV_START,
    CONTROL_REFERENCE_ID,
    DESCRIPTION,
    NAME,
    RECURRENT_SCHEDULE,
    REFERENCE_ID,
    REQUIRES_EVIDENCE,
    SECTION_CHIP_DIV_START,
    SORT_ORDER,
    SUGGESTED_OWNER,
    TL_SECTION_END,
    TL_SECTION_START,
)
from blueprint.models import ActionItemBlueprint, ControlBlueprint, TagBlueprint
from laika.utils.InputFilter import InputFilter


class ReferenceIDFilter(InputFilter):
    parameter_name = 'reference_id'
    title = 'Reference ID'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(reference_id__icontains=self.value().strip())


class NameFilter(InputFilter):
    parameter_name = 'name'
    title = 'Name'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(name__icontains=self.value().strip())


class ControlsFilter(InputFilter):
    parameter_name = 'controls_blueprint'
    title = 'Controls'
    description = 'A space separated values'

    def queryset(self, request, queryset):
        if self.value():
            filter_query = Q()
            for item in self.value().strip().split(' '):
                filter_query.add(
                    Q(controls_blueprint__reference_id__icontains=item), Q.OR
                )
            return queryset.filter(filter_query)


@admin.register(ActionItemBlueprint)
class ActionItemBlueprintAdmin(BlueprintAdmin):
    blueprint_page_name = str(BlueprintPage.ACTION_ITEMS)
    airtable_tab_name = ACTION_ITEMS_AIRTABLE_NAME
    blueprint_required_fields = ACTION_ITEM_REQUIRED_FIELDS
    blueprint_formula = BLUEPRINT_FORMULA

    blueprint_model = ActionItemBlueprint
    model_parameter_name = 'reference_id'
    blueprint_parameter_name_value = REFERENCE_ID

    ordering = ('reference_id',)

    def formatted_reference_id(self, obj):
        url = f'/admin/blueprint/actionitemblueprint/{obj.id}/change'
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

    def formatted_schedule(self, obj):
        if not obj.recurrent_schedule:
            return '-'

        if ActionItemFrequency.values.index(obj.recurrent_schedule):
            print()
        div_start = CHIP_DIV_START.format(random_color='#d7e6f5')

        return format_html(div_start + obj.recurrent_schedule + CHIP_DIV_END)

    formatted_schedule.short_description = 'Recurrent Schedule'  # type: ignore
    formatted_schedule.admin_order_field = 'recurrent_schedule'  # type: ignore

    def formatted_controls(self, instance):
        controls = []
        for control in instance.controls_blueprint.all():
            div_start = SECTION_CHIP_DIV_START.format(random_color='#d0ecf0')
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

    formatted_controls.short_description = 'Linked Controls'  # type: ignore

    def formatted_tags(self, instance):
        tags = []
        for tag in instance.tags.all():
            div_start = SECTION_CHIP_DIV_START.format(random_color='#d0ecf0')
            url = f'/admin/blueprint/controlblueprint/{tag.name}/change'
            tags.append(
                ANCHOR + url + '">' + div_start + tag.name + CHIP_DIV_END + ANCHOR_END
            )

        if not len(tags):
            return '-'
        return format_html(TL_SECTION_START + ''.join(tags) + TL_SECTION_END)

    formatted_tags.short_description = 'Tags'  # type: ignore

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

    official_fields = (
        'formatted_reference_id',
        'formatted_name',
        'formatted_description',
        'formatted_schedule',
        'is_recurrent',
        'is_required',
        'requires_evidence',
        'formatted_controls',
        'formatted_tags',
        'suggested_owner',
        'display_id',
        'airtable_record_id',
        'updated_at',
    )

    list_display = official_fields
    fields = official_fields

    list_filter = (
        ReferenceIDFilter,
        NameFilter,
        ControlsFilter,
        'recurrent_schedule',
        'requires_evidence',
        'is_recurrent',
        'is_required',
    )

    def get_related_table_records(self, request) -> Optional[dict]:
        return get_roles_records(request)

    def get_default_fields(self, fields, related_table_records: Optional[dict]) -> dict:
        requires_evidence = fields.get(REQUIRES_EVIDENCE, '').capitalize()
        requires_evidence = True if requires_evidence == 'Yes' else False

        recurrent_schedule = fields.get(RECURRENT_SCHEDULE, '')
        is_recurrent = False if not recurrent_schedule else bool(recurrent_schedule)

        formatted_description = markdown.markdown(str(fields.get(DESCRIPTION)))

        role = None

        if related_table_records:
            for record_id in fields.get(SUGGESTED_OWNER, []):
                role = related_table_records.get(record_id, {}).get(NAME)

        if role and role not in SuggestedOwner.values:
            logger.warning('Role is not a valid value')
            role = None

        return {
            'name': fields.get(NAME),
            'description': formatted_description,
            'is_required': not is_recurrent,
            'is_recurrent': is_recurrent,
            'suggested_owner': role,
            'recurrent_schedule': recurrent_schedule,
            'requires_evidence': requires_evidence,
            'display_id': get_sort_order(fields),
        }

    def execute_after_update_or_create(self, fields: dict, action_item):
        associate_action_item_controls(fields, action_item)
        set_action_item_tags(action_item, fields)
        return True


def associate_action_item_controls(fields, action_item):
    control_reference_ids = fields.get(CONTROL_REFERENCE_ID) or []

    for control_reference_id in control_reference_ids:
        try:
            control = ControlBlueprint.objects.get(reference_id=control_reference_id)
            control.action_items.add(action_item)
        except ControlBlueprint.DoesNotExist as e:
            logger.warning(f'Control {control_reference_id} does not exist: {e}')


def get_sort_order(fields):
    sort_order = fields.get(SORT_ORDER)
    if not isinstance(sort_order, int):
        sort_order = 9999999
    return sort_order


def set_action_item_tags(action_item: ActionItemBlueprint, fields: Dict):
    action_item.tags.set([])
    tags_to_create = []
    for tag_id in fields.get('Tags') or []:
        tag = TagBlueprint.objects.filter(airtable_record_id=tag_id).first()
        if tag:
            tags_to_create.append(tag)

    if tags_to_create:
        action_item.tags.set(tags_to_create)
