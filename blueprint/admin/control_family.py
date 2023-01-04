import logging

from django.contrib import admin
from django.utils.html import format_html

from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.choices import BlueprintPage
from blueprint.constants import (
    CHIP_DIV_END,
    CHIP_DIV_START,
    CONTROL_FAMILY_AIRTABLE_NAME,
    CONTROL_FAMILY_REQUIRED_FIELDS,
)
from blueprint.helpers import get_attachment
from blueprint.models import ControlFamilyBlueprint
from laika.utils.InputFilter import InputFilter

logger = logging.getLogger(__name__)


class NameFilter(InputFilter):
    parameter_name = 'name'
    title = 'Name'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(name__icontains=self.value().strip())


@admin.register(ControlFamilyBlueprint)
class ControlFamilyBlueprintAdmin(BlueprintAdmin):
    blueprint_page_name = str(BlueprintPage.CONTROL_FAMILY)
    airtable_tab_name = CONTROL_FAMILY_AIRTABLE_NAME
    blueprint_required_fields = CONTROL_FAMILY_REQUIRED_FIELDS
    blueprint_model = ControlFamilyBlueprint
    model_parameter_name = 'name'
    blueprint_parameter_name_value = 'Name'

    def family_name(self, obj):
        url = f'/admin/blueprint/controlfamilyblueprint/{obj.id}/change'
        return format_html('<a href="{}">{}</a>', url, obj)

    family_name.short_description = 'Name'  # type: ignore

    search_fields = (
        'name',
        'acronym',
    )
    official_fields = (
        'family_acronym',
        'family_name',
        'logo',
        'airtable_record_id',
        'updated_at',
    )
    list_display = official_fields
    fields = official_fields

    readonly_fields = [
        'illustration_image',
    ]

    list_filter = (NameFilter,)

    def family_acronym(self, obj):
        return format_html(
            CHIP_DIV_START.format(random_color='#d8d3dc') + obj.acronym + CHIP_DIV_END
        )

    def logo(self, obj):
        link_to = '<a href="{url}" target="_blank">View</a>'.format(
            url=obj.illustration.url
        )

        return format_html(
            '<img src="{url}" width="{width}" height={height} />'.format(
                url=obj.illustration.url,
                width=100,
                height=100,
            )
            + link_to
        )

    def illustration_image(self, obj):
        return format_html(
            '<img src="{url}" width="{width}" height={height} />'.format(
                url=obj.illustration.url,
                width=500,
                height=500,
            )
        )

    def get_default_fields(self, fields: dict, _) -> dict:
        return {
            'acronym': fields.get('Acronym'),
            'description': fields.get('Description') or '',
            'illustration': get_attachment(fields.get('Illustration')),
        }
