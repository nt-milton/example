import logging
from datetime import datetime
from multiprocessing.pool import ThreadPool
from typing import Dict, Optional, Tuple

import reversion
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path
from django.utils.html import format_html
from django.views.decorators.http import require_GET
from reversion.admin import VersionAdmin

from blueprint.admin.shared import get_framework_tag_records
from blueprint.choices import BlueprintPage
from blueprint.commons import AirtableSync
from blueprint.constants import (
    AIRTABLE_RECORD_ID,
    ANCHOR,
    ANCHOR_END,
    CERTIFICATION_SECTION_NAME,
    CHIP_DIV_END,
    CHIP_DIV_START,
    FRAMEWORK_NAME,
    FRAMEWORK_REQUIRED_FIELDS,
    FRAMEWORK_TAG,
    NAME,
    RESPONSE_REDIRECT_PATH,
    SECTION_CHIP_DIV_START,
    SECTION_NAMES,
    SECTIONS_REQUIRED_FIELDS,
    TL_SECTION_END,
    TL_SECTION_START,
)
from blueprint.models import Page
from blueprint.models.control import ControlCertificationSectionBlueprint
from certification.models import Certification, CertificationSection
from laika.utils.InputFilter import InputFilter
from user.models import User

logger = logging.getLogger(__name__)
pool = ThreadPool()


class NameFilter(InputFilter):
    parameter_name = 'name'
    title = 'Name'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(name__icontains=self.value().strip())


class SectionNameFilter(InputFilter):
    parameter_name = 'section_name'
    title = 'Section Name'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(sections__name__icontains=self.value().strip())


class CodeFilter(InputFilter):
    parameter_name = 'code'
    title = 'Code'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(code__icontains=self.value().strip())


class CertificationProxy(Certification):
    class Meta:
        proxy = True
        verbose_name = 'Certification'
        verbose_name_plural = 'Certification Blueprint'


@admin.register(CertificationProxy)
class CertificationBlueprintAdmin(VersionAdmin):
    ordering = ('-code',)

    def formatted_ftag(self, instance):
        if not instance.code:
            return '-'

        url = f'/admin/blueprint/certificationproxy/{instance.id}/change'

        return format_html(
            '<a href="'
            + url
            + '">'
            + CHIP_DIV_START.format(random_color='#d8d3dc')
            + instance.code
            + CHIP_DIV_END
            + '</a>'
        )

    formatted_ftag.short_description = 'Framework Tag'  # type: ignore

    def formatted_linked_controls(self, instance):
        controls = []
        sections = ControlCertificationSectionBlueprint.objects.filter(
            certification_section__certification_id=instance.id
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

    def formatted_sections(self, instance):
        sections = []
        for relation in instance.sections.all().order_by('name'):
            # '#95bde5'
            div_start = SECTION_CHIP_DIV_START.format(random_color='#d8d3dc')
            url = f'/admin/blueprint/certificationsectionproxy/{relation.id}/change'

            sections.append(
                '<a href="'
                + url
                + '">'
                + div_start
                + relation.name
                + CHIP_DIV_END
                + '</a>'
            )

        return format_html(TL_SECTION_START + ''.join(sections) + TL_SECTION_END)

    formatted_sections.short_description = 'Linked Sections'  # type: ignore

    def formatted_logo(self, obj):
        if not obj.logo:
            return '-'

        link_to = '<a href="{url}" target="_blank">View</a>'.format(url=obj.logo.url)

        return format_html(
            '<img src="{url}" width="{width}" height={height} />'.format(
                url=obj.logo.url,
                width=60,
                height=60,
            )
            + link_to
        )

    formatted_logo.short_description = 'Logo'  # type: ignore

    official_fields = (
        'name',
        'formatted_ftag',
        'is_visible',
        'formatted_logo',
        'formatted_sections',
        'formatted_linked_controls',
        'airtable_record_id',
        'updated_at',
    )
    list_display = official_fields
    fields = official_fields

    list_filter = (
        NameFilter,
        CodeFilter,
        SectionNameFilter,
        'is_visible',
    )
    search_fields = ('name',)

    actions = None
    change_list_template = 'admin/control_change_list.html'
    change_form_template = 'admin/blueprint_change_form.html'

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


def get_airtable_sync_class(request) -> Optional[AirtableSync]:
    if not Page.objects.filter(name=BlueprintPage.CERTIFICATION).exists():
        messages.warning(request, 'Blueprint Certification does not exist')
        return None

    sections = get_related_table(request)
    framework_tags = get_framework_tag_related_table(request)

    return AirtableSync(
        table_name='Frameworks',
        blueprint_name=BlueprintPage.CERTIFICATION,
        required_fields=FRAMEWORK_REQUIRED_FIELDS,
        request_user=request.user,
        raw_formula="NOT({Framework Tag} = '')",
        related_table_records={'sections': sections, 'framework_tags': framework_tags},
    )


@require_GET
def sync_record_from_airtable(request, record_id):
    certification = Certification.objects.get(id=record_id)
    if not certification.airtable_record_id:
        messages.warning(request, 'This object does not have a link to airtable')
        return HttpResponseRedirect(RESPONSE_REDIRECT_PATH)

    airtable = get_airtable_sync_class(request)
    if airtable:
        airtable.update_single_record_of_blueprint(
            certification.airtable_record_id,
            upsert_object=update_or_create_certification,
        )
        messages.info(request, 'Certification updated!')
    return HttpResponseRedirect(RESPONSE_REDIRECT_PATH)


@require_GET
def sync_from_airtable(request):
    messages.info(request, 'Sync is running in the background')

    airtable = get_airtable_sync_class(request)
    if airtable:
        pool.apply_async(init_update, args=(airtable,))

    return HttpResponseRedirect(RESPONSE_REDIRECT_PATH)


def init_update(airtable: Optional[AirtableSync]):
    if airtable:
        set_certification_sections_blueprint_status_detail('')

        return airtable.update_blueprint(upsert_object=update_or_create_certification)
    return False


def set_certification_blueprint_status_detail(detail: str = ''):
    Page.objects.filter(name=BlueprintPage.CERTIFICATION).update(status_detail=detail)


def set_certification_sections_blueprint_status_detail(detail: str = ''):
    Page.objects.filter(name=BlueprintPage.CERTIFICATION_SECTIONS).update(
        status_detail=detail
    )


def get_framework_tag_related_table(request) -> Dict:
    try:
        return get_framework_tag_records(request)
    except Exception as e:
        message = f'Error getting framework tag records from airtable: {e}'
        logger.warning(message)
        set_certification_blueprint_status_detail(message)
        messages.warning(request, message)
        return {}


def get_related_table(request) -> Dict:
    try:
        sections_airtable = AirtableSync(
            table_name='Framework Reference (Core Controls)',
            blueprint_name=BlueprintPage.CERTIFICATION,
            required_fields=SECTIONS_REQUIRED_FIELDS,
            request_user=request.user,
        )

        sections = {}
        for record in sections_airtable.get_airtable_records():
            fields = sections_airtable.get_record_fields(record)
            if not fields:
                continue

            sections[record.get('id')] = fields

        return sections
    except Exception as e:
        message = f'Error getting airtable records: {e}'
        logger.warning(message)
        set_certification_sections_blueprint_status_detail(message)
        messages.warning(request, message)
        return {}


def update_or_create_certification(fields, request_user, related_table):
    certification, created, updated = update_or_create_django_certification(
        fields, request_user, related_table
    )

    for section_record_id in fields.get(SECTION_NAMES):
        create_sections(certification, related_table, section_record_id)

    update_certification_sections_blueprint(certification.name)
    return certification, created, updated


def update_or_create_django_certification(
    fields: Dict,
    request_user: User,
    related_table: Dict,
) -> Tuple[Certification, bool, bool]:
    with reversion.create_revision():
        reversion.set_comment('Synced from Airtable')
        reversion.set_user(request_user)
        code = get_certification_code(fields, related_table)

        exists = Certification.objects.filter(name=fields.get(FRAMEWORK_NAME)).exists()

        if exists:
            return update_certification(fields, code)
        return create_certification(fields, code)


def create_sections(
    certification: Certification, related_table: Dict, section_record_id: str
):
    section = related_table.get('sections', {}).get(section_record_id)

    if section:
        cert_section, _ = CertificationSection.objects.update_or_create(
            name=section.get(CERTIFICATION_SECTION_NAME),
            certification=certification,
            defaults={'airtable_record_id': section.get(AIRTABLE_RECORD_ID)},
        )


def update_certification_sections_blueprint(certification_name: str):
    blueprint = Page.objects.get(name=BlueprintPage.CERTIFICATION_SECTIONS)

    message = (
        f'Certification Sections for {certification_name} were created successfully.'
    )

    blueprint.status_detail += '\n' + message + '\n'
    blueprint.synched_at = datetime.now()
    blueprint.save()

    logger.info(message)


def get_certification_code(fields: dict, related_table: dict) -> str:
    code = ''
    for record_id in fields.get(FRAMEWORK_TAG, []):
        code = related_table.get('framework_tags', {}).get(record_id, {}).get(NAME)
    return code or ''


def create_certification(fields: dict, code: str) -> Tuple[Certification, bool, bool]:
    code_count = Certification.objects.filter(code=code).count()
    certification = Certification.objects.create(
        name=fields.get(FRAMEWORK_NAME),
        airtable_record_id=fields.get(AIRTABLE_RECORD_ID),
        code='',
        regex='',
    )

    if code_count == 0:
        certification.code = code
        certification.save()
    else:
        logger.warning(f'There is another framework with the same code: {code}')

    return certification, True, False


def update_certification(fields: dict, code: str) -> Tuple[Certification, bool, bool]:
    code_count = Certification.objects.filter(code=code).count()
    cert = Certification.objects.get(name=fields.get(FRAMEWORK_NAME))
    cert.airtable_record_id = fields.get(AIRTABLE_RECORD_ID)

    if (code_count == 1 and cert.code == code) or code_count == 0:
        cert.code = code
    else:
        logger.warning(f'There is another framework with the same code: {code}')
    cert.save()
    return cert, False, True
