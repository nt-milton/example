from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path
from django.utils.html import format_html
from django.views.decorators.http import require_GET
from reversion.admin import VersionAdmin

from blueprint.constants import (
    ANCHOR,
    ANCHOR_END,
    CHIP_DIV_END,
    CHIP_DIV_START,
    RESPONSE_REDIRECT_PATH,
    SECTION_CHIP_DIV_START,
    TL_SECTION_END,
    TL_SECTION_START,
)
from blueprint.models.control import ControlCertificationSectionBlueprint
from certification.models import CertificationSection
from laika.utils.InputFilter import InputFilter


class CertificationNameFilter(InputFilter):
    parameter_name = 'certification'
    title = 'Certification'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(certification__name__icontains=self.value().strip())


class ControlFilter(InputFilter):
    parameter_name = 'control'
    title = 'Linked Control (Reference ID)'

    def queryset(self, request, queryset):
        if self.value():
            section_ids = ControlCertificationSectionBlueprint.objects.filter(
                control__reference_id__contains=self.value().strip(),
            ).values_list('certification_section__id', flat=True)

            return queryset.filter(id__in=section_ids)


class CertificationSectionProxy(CertificationSection):
    class Meta:
        proxy = True
        verbose_name = 'Certification Sections'
        verbose_name_plural = 'Certification Sections Blueprint'


@admin.register(CertificationSectionProxy)
class CertificationSectionBlueprintAdmin(VersionAdmin):
    model = CertificationSectionProxy
    ordering = ('name',)

    def formatted_linked_controls(self, instance):
        controls = []
        sections = ControlCertificationSectionBlueprint.objects.filter(
            certification_section=instance
        )

        for relation in sections:
            div_start = SECTION_CHIP_DIV_START.format(random_color='#d8d3dc')

            url = f'/admin/blueprint/controlblueprint/{relation.control.id}/change'

            controls.append(
                ANCHOR
                + url
                + '">'
                + div_start
                + relation.control.reference_id
                + CHIP_DIV_END
                + ANCHOR_END
            )

        if not len(controls):
            return '-'
        return format_html(TL_SECTION_START + ''.join(controls) + TL_SECTION_END)

    formatted_linked_controls.short_description = 'Controls'  # type: ignore

    def formatted_framework(self, instance):
        url = f'/admin/certification/certification/{instance.certification.id}/change'
        return format_html(
            ANCHOR
            + url
            + '">'
            + CHIP_DIV_START.format(random_color='#d8d3dc')
            + instance.certification.name
            + CHIP_DIV_END
            + ANCHOR_END
        )

    formatted_framework.short_description = 'Framework'  # type: ignore
    formatted_framework.admin_order_field = 'certification'  # type: ignore

    official_fields = (
        'name',
        'formatted_framework',
        'formatted_linked_controls',
        'airtable_record_id',
        'updated_at',
    )

    list_display = official_fields
    fields = official_fields

    list_filter = (
        CertificationNameFilter,
        ControlFilter,
    )
    search_fields = (
        'name',
        'certification__name',
    )
    actions = None

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('sync_from_airtable/', sync_from_airtable),
            path(
                '<str:record_id>/change/sync_record_from_airtable/',
                sync_record_from_airtable,
            ),
        ]
        return custom_urls + urls


@require_GET
def sync_record_from_airtable(request, record_id):
    messages.info(request, 'Action not supported for this view')
    return HttpResponseRedirect(RESPONSE_REDIRECT_PATH)


@require_GET
def sync_from_airtable(request):
    messages.info(request, 'Action not supported for this view')
    return HttpResponseRedirect(RESPONSE_REDIRECT_PATH)
