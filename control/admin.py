import logging

from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db.models import Value
from django.db.models.functions import Concat
from django.forms import ModelChoiceField, ModelForm, ModelMultipleChoiceField
from django.utils.html import format_html
from reversion.admin import VersionAdmin

from action_item.models import ActionItem
from blueprint.constants import (
    ANCHOR,
    ANCHOR_END,
    CHIP_DIV_END,
    SECTION_CHIP_DIV_START,
    TL_SECTION_END,
    TL_SECTION_START,
)
from certification.models import CertificationSection, UnlockedOrganizationCertification
from laika.utils.InputFilter import InputFilter
from tag.models import Tag

from .models import Control, ControlGroup, ControlPillar, RoadMap

logger = logging.getLogger(__name__)


class OrganizationFilter(InputFilter):
    parameter_name = 'organization_name'
    title = 'Organization Name'
    description = 'Name should be exact. Case insensitive'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(organization__name__iexact=self.value().strip())


class PillarFilter(InputFilter):
    parameter_name = 'pillar_name'
    title = 'Pillar Name'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(pillar__name__icontains=self.value().strip())


class ReferenceIdFilter(InputFilter):
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


class GroupNameFilter(InputFilter):
    parameter_name = 'group_name'
    title = 'Group Name'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(group__name__icontains=self.value().strip())


class CertificationSectionChoiceField(ModelMultipleChoiceField):
    def label_from_instance(self, cert_sect):
        return cert_sect.new_name


class ControlForm(ModelForm):
    group = ModelChoiceField(required=False, queryset=ControlGroup.objects.all())

    certification_sections = CertificationSectionChoiceField(
        required=False,
        queryset=CertificationSection.objects.all(),
        widget=FilteredSelectMultiple(
            'Certification Sections', False, attrs={'rows': '10'}
        ),
    )

    tags = ModelMultipleChoiceField(
        required=False,
        queryset=Tag.objects.all(),
        widget=FilteredSelectMultiple('Tags', False, attrs={'rows': '10'}),
    )

    action_items = ModelMultipleChoiceField(
        required=False,
        queryset=ActionItem.objects.all().order_by('name'),
        widget=FilteredSelectMultiple('Action Items', False, attrs={'rows': '10'}),
    )

    def __init__(self, *args, **kwargs):
        if 'instance' in kwargs and kwargs['instance']:
            initial = kwargs.setdefault('initial', {})

            initial['group'] = [
                str(group.pk) for group in kwargs['instance'].group.all()
            ]

            initial['tags'] = [
                tag.pk for tag in kwargs['instance'].tags.all().order_by('name')
            ]

            initial['certification_sections'] = [
                cert_sect.pk
                for cert_sect in kwargs['instance']
                .certification_sections.all()
                .order_by('name')
            ]

            instance = kwargs['instance']

            # Filter by Control.organization_id
            self.base_fields['group'].queryset = ControlGroup.objects.filter(
                roadmap__organization_id=instance.organization_id
            )
            self.base_fields['tags'].queryset = Tag.objects.filter(
                organization_id=instance.organization_id
            ).order_by('name')

            self.base_fields['certification_sections'].queryset = (
                CertificationSection.objects.filter(
                    certification_id__in=(
                        UnlockedOrganizationCertification.objects.filter(
                            organization_id=instance.organization_id
                        ).values('certification_id')
                    )
                )
                .annotate(new_name=Concat('certification__name', Value(' - '), 'name'))
                .order_by('new_name')
            )

            self.base_fields['action_items'].queryset = ActionItem.objects.filter(
                metadata__organizationId=str(instance.organization_id),
            ).order_by('name')
        super(ControlForm, self).__init__(*args, **kwargs)

    def save_m2m(self):
        group = self.cleaned_data['group']
        self.instance.group.set([])

        if group:
            self.instance.group.add(group)

        for tag in self.cleaned_data['tags']:
            self.instance.tags.add(tag)

        for action_item in self.cleaned_data['action_items']:
            self.instance.action_items.add(action_item)

        for section in self.cleaned_data['certification_sections']:
            self.instance.certification_sections.add(section)

    def save(self, *args, **kwargs):
        instance = super(ControlForm, self).save()
        self.save_m2m()
        return instance

    class Meta:
        model = Control
        fields = [
            'id',
            'organization',
            'name',
            'display_id',
            'reference_id',
            'household',
            'description',
            'implementation_notes',
            'implementation_guide_blueprint',
            'pillar',
            'certification_sections',
            'tags',
            'framework_tag',
        ]


class ControlAdmin(VersionAdmin):
    model = Control
    form = ControlForm

    def formatted_group(self, obj):
        group_links = []
        for group in obj.group.iterator():
            div_start = SECTION_CHIP_DIV_START.format(random_color='#d8d3dc')
            url = f'/admin/control/controlgroup/{group.id}/change'
            group_links.append(
                ANCHOR + url + '">' + div_start + group.name + CHIP_DIV_END + ANCHOR_END
            )
        if not len(group_links):
            return '-'
        return format_html(TL_SECTION_START + ''.join(group_links) + TL_SECTION_END)

    formatted_group.short_description = 'Linked Group'  # type: ignore

    list_display = (
        'reference_id',
        'display_id',
        'name',
        'formatted_group',
        'pillar',
        'status',
        'organization',
        'created_at',
    )

    search_fields = (
        'name',
        'reference_id',
    )
    list_filter = [
        OrganizationFilter,
        ReferenceIdFilter,
        NameFilter,
        GroupNameFilter,
        PillarFilter,
        'status',
    ]
    ordering = (
        'display_id',
        '-created_at',
    )
    readonly_fields = ['created_at', 'updated_at']

    def group_name(self, instance):
        return instance.group.name if instance.group else '-'


class ControlPillarAdmin(VersionAdmin):
    model = ControlPillar
    list_display = (
        'name',
        'acronym',
        'description',
    )
    search_fields = (
        'name',
        'acronym',
    )
    list_filter = ('acronym',)


class RoadMapAdmin(VersionAdmin):
    model = RoadMap
    organization_tuple = ('organization',)
    list_display = organization_tuple
    list_filter = organization_tuple
    ordering = organization_tuple


class GroupChoiceField(ModelChoiceField):
    def label_from_instance(self, group):
        return group.sort_order


class OrganizationFilterForGroup(InputFilter):
    parameter_name = 'organization_name'
    title = 'Organization Name'
    description = 'Name should be exact. Case insensitive'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                roadmap__organization__name__iexact=self.value().strip()
            )


class ControlGroupForm(ModelForm):
    custom_order = GroupChoiceField(
        label='Sort Order', required=False, queryset=ControlGroup.objects.all()
    )

    controls = ModelMultipleChoiceField(
        required=False,
        queryset=Control.objects.all(),
        widget=FilteredSelectMultiple('Controls', False, attrs={'rows': '10'}),
    )

    def __init__(self, *args, **kwargs):
        if 'instance' in kwargs and kwargs['instance']:
            initial = kwargs.setdefault('initial', {})
            instance = kwargs['instance']

            initial['custom_order'] = str(instance.pk)
            initial['controls'] = [
                str(control.pk) for control in instance.controls.all()
            ]

            self.base_fields['custom_order'].queryset = ControlGroup.objects.filter(
                roadmap__organization_id=instance.roadmap.organization_id
            ).order_by('sort_order')

            all_controls = Control.objects.filter(
                organization_id=instance.roadmap.organization_id
            ).order_by('display_id')

            self.base_fields['controls'].queryset = all_controls
        super(ControlGroupForm, self).__init__(*args, **kwargs)

    def save_m2m(self):
        selected_group = self.cleaned_data['custom_order']
        new_sort_order = selected_group.sort_order
        current_order = self.instance.sort_order

        side_group = ControlGroup.objects.get(
            roadmap__organization_id=self.instance.roadmap.organization_id,
            sort_order=new_sort_order,
        )
        side_group.sort_order = current_order
        side_group.save()

        self.instance.sort_order = new_sort_order

        controls = [control for control in self.cleaned_data['controls']]

        for control in controls:
            control.group.set([])
            control.save()
            self.instance.controls.add(control)

    def save(self, *args, **kwargs):
        instance = super(ControlGroupForm, self).save()
        self.save_m2m()
        return instance

    class Meta:
        model = ControlGroup
        fields = [
            'id',
            'name',
            'roadmap',
            'reference_id',
            'controls',
            'start_date',
            'due_date',
        ]


class ControlGroupAdmin(VersionAdmin):
    model = ControlGroup
    form = ControlGroupForm
    list_display = ('name', 'roadmap', 'reference_id', 'sort_order')

    search_fields = (
        'name',
        'roadmap__organization__name',
    )
    list_filter = (OrganizationFilterForGroup,)
    ordering = (
        '-roadmap__organization__created_at',
        'sort_order',
    )


admin.site.register(Control, ControlAdmin)
admin.site.register(ControlPillar, ControlPillarAdmin)
admin.site.register(RoadMap, RoadMapAdmin)
admin.site.register(ControlGroup, ControlGroupAdmin)
