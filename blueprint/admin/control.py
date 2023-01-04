import logging
from typing import Dict, List, Optional

from django.contrib import admin
from django.utils.html import format_html

from blueprint.admin.blueprint_base import BlueprintAdmin
from blueprint.admin.shared import get_framework_tag_records, get_roles_records
from blueprint.choices import BlueprintPage, SuggestedOwner
from blueprint.constants import (
    ANCHOR,
    ANCHOR_END,
    BLUEPRINT_FORMULA,
    CHIP_DIV_END,
    CHIP_DIV_START,
    CONTROL_FAMILY_REFERENCES,
    CONTROL_REQUIRED_FIELDS,
    DESCRIPTION,
    FRAMEWORK_TAG,
    HOUSEHOLD,
    NAME,
    REFERENCE_ID,
    SECTION_CHIP_DIV_START,
    SORT_ORDER_WITHIN_GROUP,
    SUGGESTED_OWNER,
    TL_SECTION_END,
    TL_SECTION_START,
)
from blueprint.models import (
    ControlBlueprint,
    ControlFamilyBlueprint,
    ControlGroupBlueprint,
    ImplementationGuideBlueprint,
    TagBlueprint,
)
from blueprint.models.control import ControlCertificationSectionBlueprint
from certification.models import Certification, CertificationSection
from laika.utils.exceptions import ServiceException
from laika.utils.InputFilter import InputFilter

logger = logging.getLogger(__name__)


class NameFilter(InputFilter):
    parameter_name = 'name'
    title = 'Name'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(name__icontains=self.value().strip())


class FamilyFilter(InputFilter):
    parameter_name = 'family'
    title = 'Family'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(family__name__icontains=self.value().strip())


class ReferenceIDFilter(InputFilter):
    parameter_name = 'reference_id'
    title = 'Reference ID'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(reference_id__icontains=self.value().strip())


class HouseholdFilter(InputFilter):
    parameter_name = 'household'
    title = 'Household'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(household__icontains=self.value().strip())


class GroupFilter(InputFilter):
    parameter_name = 'group'
    title = 'Group'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(group__name__icontains=self.value().strip())


class FrameworkTagFilter(InputFilter):
    parameter_name = 'framework_tag'
    title = 'Framework Tag'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(framework_tag__icontains=self.value().strip())


class CertificationsFilter(InputFilter):
    title = 'Certification'
    parameter_name = 'certification'

    def queryset(self, request, queryset):
        if not self.value():
            return

        return queryset.filter(
            certification_sections__certification__name__icontains=self.value()
        )


@admin.register(ControlBlueprint)
class ControlBlueprintAdmin(BlueprintAdmin):
    blueprint_page_name = str(BlueprintPage.CONTROLS)
    airtable_tab_name = 'Controls'
    blueprint_required_fields = CONTROL_REQUIRED_FIELDS
    blueprint_formula = BLUEPRINT_FORMULA
    blueprint_model = ControlBlueprint
    model_parameter_name = 'reference_id'
    blueprint_parameter_name_value = REFERENCE_ID

    framework_names = []

    def should_show_prescribe_button(self) -> bool:
        return True

    def get_framework_names(self):
        if not self.framework_names:
            self.framework_names = list(
                Certification.objects.filter(
                    airtable_record_id__isnull=False, airtable_record_id__gt=''
                ).values_list('name', flat=True)
            )
        return self.framework_names

    def formatted_reference_id(self, obj):
        url = f'/admin/blueprint/controlblueprint/{obj.id}/change'
        return format_html(
            ANCHOR
            + url
            + '">'
            + CHIP_DIV_START.format(random_color='#d8d3dc')
            + obj.reference_id
            + CHIP_DIV_END
            + '</a>'
        )

    formatted_reference_id.short_description = 'Reference ID'  # type: ignore
    formatted_reference_id.admin_order_field = 'reference_id'  # type: ignore

    def formatted_household(self, obj):
        url = f'/admin/blueprint/controlblueprint/{obj.id}/change'
        return format_html(
            ANCHOR
            + url
            + '">'
            + CHIP_DIV_START.format(random_color='#d8d3dc')
            + obj.household
            + CHIP_DIV_END
            + ANCHOR_END
        )

    formatted_household.short_description = 'Household'  # type: ignore
    formatted_household.admin_order_field = 'household'  # type: ignore

    def formatted_name(self, obj):
        return format_html('<div style="min-width: 250px;">' + obj.name + CHIP_DIV_END)

    formatted_name.short_description = 'Name'  # type: ignore
    formatted_name.admin_order_field = 'name'  # type: ignore

    def formatted_ftag(self, obj):
        cert = Certification.objects.get(code=obj.framework_tag)

        url = f'/admin/blueprint/certificationproxy/{cert.id}/change'
        div_start = CHIP_DIV_START.format(random_color='#d8d3dc')
        return format_html(
            ANCHOR
            + url
            + '">'
            + div_start
            + obj.framework_tag
            + CHIP_DIV_END
            + ANCHOR_END
        )

    formatted_ftag.short_description = 'Framework Tag'  # type: ignore

    def formatted_family(self, obj):
        url = f'/admin/blueprint/controlfamilyblueprint/{obj.family.id}/change'
        return format_html(
            ANCHOR
            + url
            + '">'
            + CHIP_DIV_START.format(random_color='#d8d3dc')
            + obj.family.name
            + CHIP_DIV_END
            + ANCHOR_END
        )

    formatted_family.short_description = 'Family'  # type: ignore
    formatted_family.admin_order_field = 'family'  # type: ignore

    def formatted_certifications(self, obj):
        raw_sections = []
        sections = []
        for section in obj.certification_sections.iterator():
            div_start = SECTION_CHIP_DIV_START.format(random_color='#d8d3dc')

            if section.certification.name in raw_sections:
                continue

            url = (
                f'/admin/blueprint/certificationproxy/{section.certification.id}/change'
            )
            raw_sections.append(section.certification.name)
            sections.append(
                ANCHOR
                + url
                + '">'
                + div_start
                + section.certification.name
                + CHIP_DIV_END
                + '</a>'
            )

        if not len(sections):
            return '-'
        return format_html(TL_SECTION_START + ''.join(sections) + TL_SECTION_END)

    formatted_certifications.short_description = 'Frameworks'  # type: ignore

    def formatted_sections(self, obj):
        frameworks = {}
        for section in obj.certification_sections.iterator():
            if not frameworks.get(section.certification.name):
                frameworks.update({section.certification.name: []})
            frameworks[section.certification.name].append(section)

        sections_html = ''
        for framework in frameworks:
            html = '<div class="field-framework-sections">'
            for section in frameworks.get(framework):
                div_start = SECTION_CHIP_DIV_START.format(random_color='#d8d3dc')

                url = f'/admin/blueprint/certificationsectionproxy/{section.id}/change'

                html += (
                    ANCHOR
                    + url
                    + '">'
                    + div_start
                    + section.name
                    + CHIP_DIV_END
                    + ANCHOR_END
                )
            html += '</div>'

            sections_html += '''
                <div class="framework-block">
                    <h3 class="framework-title">{framework}</h3>
                    {html}
                </div>
            '''.format(
                framework=framework, html=html
            )
        return format_html(sections_html)

    formatted_sections.short_description = 'Frameworks'  # type: ignore

    def formatted_group(self, obj):
        url = f'/admin/blueprint/controlgroupblueprint/{obj.group.id}/change'
        return format_html(
            ANCHOR
            + url
            + '">'
            + CHIP_DIV_START.format(random_color='#d8d3dc')
            + obj.group.name
            + CHIP_DIV_END
            + ANCHOR_END
        )

    formatted_group.short_description = 'Group'  # type: ignore

    def formatted_lais(self, instance):
        lais = []
        for control in instance.action_items.all():
            div_start = SECTION_CHIP_DIV_START.format(random_color='#d8d3dc')
            url = f'/admin/blueprint/actionitemblueprint/{control.id}/change'
            lais.append(
                ANCHOR
                + url
                + '">'
                + div_start
                + control.reference_id
                + CHIP_DIV_END
                + ANCHOR_END
            )

        if not len(lais):
            return '-'
        return format_html(TL_SECTION_START + ''.join(lais) + TL_SECTION_END)

    formatted_lais.short_description = 'Action Items'  # type: ignore

    official_fields = (
        'formatted_reference_id',
        'formatted_name',
        'formatted_household',
        'formatted_ftag',
        'formatted_group',
        'formatted_family',
        'formatted_certifications',
        'formatted_lais',
        'suggested_owner',
        'airtable_record_id',
        'display_id',
        'updated_at',
    )

    list_display = official_fields
    fields = official_fields

    list_filter = (
        ReferenceIDFilter,
        NameFilter,
        HouseholdFilter,
        FamilyFilter,
        FrameworkTagFilter,
        CertificationsFilter,
        GroupFilter,
    )

    search_fields = (
        'name',
        'certification_sections__certification__name',
    )
    readonly_fields = [
        'tags',
    ]

    def get_related_table_records(self, request) -> Optional[dict]:
        related_records = {
            'roles': get_roles_records(request),
            'framework_tags': get_framework_tag_records(request),
        }
        return related_records

    def get_default_fields(self, fields: dict, related_table_records: Optional[dict]):
        framework_tag = None
        role = None
        if related_table_records and related_table_records.get('framework_tags'):
            for record_id in fields.get(FRAMEWORK_TAG, []):
                framework_tag = (
                    related_table_records['framework_tags'].get(record_id, {}).get(NAME)
                )

        if related_table_records and related_table_records.get('roles'):
            for record_id in fields.get(SUGGESTED_OWNER, []):
                role = related_table_records['roles'].get(record_id, {}).get(NAME)

        if not framework_tag:
            raise ServiceException('Framework tag is none and it is a required field')

        if role and role not in SuggestedOwner.values:
            logger.warning('Role is not a valid value')
            role = None

        defaults = {
            'name': fields.get(NAME),
            'household': fields.get(HOUSEHOLD),
            'framework_tag': framework_tag,
            'suggested_owner': role,
            'family': get_control_family(fields.get(CONTROL_FAMILY_REFERENCES, '')),
            'description': fields.get(DESCRIPTION) or '',
            'display_id': fields.get(SORT_ORDER_WITHIN_GROUP),
        }

        status = fields.get('Status', '').upper()
        if status:
            defaults.update({'status': status})

        return defaults

    def execute_after_update_or_create(self, fields: dict, control):
        set_control_group(control, fields)
        set_control_tags(control, fields)
        set_control_implementation_guide(control, fields)
        set_control_certificate_sections(control, fields, self.get_framework_names())
        return True


def get_control_family(family_name: str) -> Optional[ControlFamilyBlueprint]:
    if not family_name:
        return None
    return ControlFamilyBlueprint.objects.get(name=family_name.strip('\"'))


def set_control_group(control: ControlBlueprint, fields: Dict):
    group = None

    groups = fields.get('Group Reference ID') or {}
    for group_airtable_id in groups:
        group = ControlGroupBlueprint.objects.filter(
            reference_id=group_airtable_id
        ).first()

    if group and control.group != group:
        control.group = group
        control.save()


def set_control_implementation_guide(control: ControlBlueprint, fields: Dict):
    guide = None

    for guide_airtable_record_id in fields.get('Implementation Guide (Linked)', []):
        guide = ImplementationGuideBlueprint.objects.filter(
            airtable_record_id=guide_airtable_record_id
        ).first()

    if guide and control.implementation_guide != guide:
        control.implementation_guide = guide
        control.save()


def set_control_tags(control: ControlBlueprint, fields: Dict):
    control.tags.set([])
    tags_to_create = []
    for tag_id in fields.get('Tags') or []:
        tag = TagBlueprint.objects.filter(airtable_record_id=tag_id).first()
        if tag:
            tags_to_create.append(tag)

    if tags_to_create:
        control.tags.set(tags_to_create)


def set_control_certificate_sections(
    control: ControlBlueprint, fields: Dict, framework_names: list[str]
):
    control.certification_sections.set([])
    for certification_name in framework_names:
        section_names = fields.get(certification_name) or []
        create_certification_section(control, section_names, certification_name)


def create_certification_section(
    control, airtable_sections: List[str], certification_name: str
):
    sections_to_create = []
    for section in airtable_sections:
        certification_section = CertificationSection.objects.filter(
            airtable_record_id=section, certification__name=certification_name
        ).first()

        if certification_section:
            sections_to_create.append(
                ControlCertificationSectionBlueprint(
                    certification_section=certification_section, control=control
                )
            )

    if sections_to_create:
        ControlCertificationSectionBlueprint.objects.bulk_create(
            objs=sections_to_create
        )
