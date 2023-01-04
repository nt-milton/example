import json
import logging

from django import forms
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.admin.widgets import AutocompleteSelect
from django.db.models import JSONField, Q
from django.forms import ModelForm, ModelMultipleChoiceField, widgets
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
from certification.models import Certification
from control.constants import MetadataFields
from control.models import Control
from laika.utils.InputFilter import InputFilter
from laika.widgets.CustomAutocompleteSelect import CustomAutocompleteSelect
from organization.models import Organization
from user.models import User

logger = logging.getLogger(__name__)


class PrettyJSONWidget(widgets.Textarea):
    def format_value(self, value):
        try:
            value = json.dumps(json.loads(value), indent=2, sort_keys=True)
            # these lines will try to adjust size of TextArea to fit to content
            row_lengths = [len(r) for r in value.split('\n')]
            self.attrs['rows'] = min(max(len(row_lengths) + 2, 10), 30)
            self.attrs['cols'] = min(max(max(row_lengths) + 2, 40), 120)
            return value
        except Exception as e:
            logger.warning("Error while formatting JSON: {}".format(e))
            return super(PrettyJSONWidget, self).format_value(value)


class OrganizationFilter(InputFilter):
    parameter_name = 'organization'
    title = 'Organization Name'
    description = 'Name should be exact. Case insensitive'

    def queryset(self, request, queryset):
        if self.value():
            org = Organization.objects.filter(name__iexact=self.value().strip()).first()

            if org:
                return queryset.filter(metadata__organizationId=str(org.id)).order_by(
                    'metadata__referenceId'
                )

            return queryset.none()


class ReferenceIdFilter(InputFilter):
    parameter_name = 'reference_id'
    title = 'Reference ID'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                metadata__referenceId__icontains=self.value().strip()
            )


class NameFilter(InputFilter):
    parameter_name = 'name'
    title = 'Name'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(name__icontains=self.value())


class EvidenceFilter(SimpleListFilter):
    title = 'Evidence Required'
    parameter_name = 'evidenceRequired'

    def lookups(self, request, model_admin):
        options = (
            ActionItem.objects.all()
            .values_list('metadata__requiredEvidence', flat=True)
            .distinct()
        )
        return [(o, o) for o in options]

    def queryset(self, request, queryset):
        if self.value() == 'True':
            param = 'true'
        else:
            param = 'false' if self.value() == 'False' else self.value()

        if self.value():
            return queryset.filter(metadata__requiredEvidence=param).order_by(
                'metadata__referenceId'
            )


class IsCustomFilter(SimpleListFilter):
    title = 'Is Custom'
    parameter_name = 'isCustom'

    def lookups(self, request, model_admin):
        options = ['Yes']
        return [(o, o) for o in options]

    def queryset(self, request, queryset):
        if self.value() == 'Yes':
            return queryset.filter(metadata__isCustom=True).order_by(
                'metadata__referenceId'
            )


class ControlsFilter(InputFilter):
    parameter_name = 'controls'
    title = 'Controls'
    description = 'A space separated values. Control Reference ID must be exact'

    def queryset(self, request, queryset):
        if self.value():
            filter_query = Q()
            for item in self.value().strip().split(' '):
                filter_query.add(Q(controls__reference_id__iexact=item), Q.OR)
            return queryset.filter(filter_query).distinct()


class FrameworksFilter(InputFilter):
    parameter_name = 'framework'
    title = 'Framework'
    description = 'Use framework name to filter'

    def queryset(self, request, queryset):
        if self.value():
            filter_query = Q()
            certs = Certification.objects.filter(name__icontains=self.value().strip())
            if not certs:
                return queryset.exclude(id__gt=0)
            for cert in certs:
                if cert.code:
                    filter_query.add(
                        Q(controls__reference_id__endswith=cert.code), Q.OR
                    )
            return queryset.filter(filter_query).distinct()


class AutocompleteChoiceField(AutocompleteSelect):
    def __init__(
        self, field, prompt="", admin_site=None, attrs=None, choices=(), using=None
    ):
        self.prompt = prompt
        super().__init__(field, admin_site, attrs=attrs, choices=choices, using=using)

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs=extra_attrs)
        attrs.update(
            {
                'data-ajax--delay': 250,
                'data-placeholder': self.prompt,
                'style': 'width: 30em;',
            }
        )
        return attrs


class ActionItemAdminForm(ModelForm):
    class Meta:
        model: ActionItem
        fields = [
            'name',
            'description',
            'parent_action_item',
            'is_required',
            'is_recurrent',
            'recurrent_schedule',
            'status',
            'completion_date',
            'due_date',
            'metadata',
            'display_id',
        ]

    name = forms.CharField(widget=forms.Textarea(attrs={'rows': 1, 'cols': 100}))

    description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 10, 'cols': 100})
    )

    assignees = ModelMultipleChoiceField(
        required=False,
        queryset=User.objects.all().order_by('first_name'),
        widget=CustomAutocompleteSelect(
            ActionItem._meta.get_field('assignees'),
            'Search for user',
            admin.site,
        ),
    )

    organization = forms.ModelChoiceField(
        required=False,
        queryset=Organization.objects.all(),
        widget=AutocompleteChoiceField(
            Control._meta.get_field('organization'),
            'Search for organization',
            admin.site,
        ),
    )

    requires_evidence = forms.BooleanField(required=False, label='Requires Evidence?')

    def __init__(self, *args, **kwargs):
        if 'instance' in kwargs and kwargs['instance']:
            initial = kwargs.setdefault('initial', {})
            instance = kwargs['instance']

            self.base_fields['is_recurrent'].disabled = True
            self.base_fields[
                'is_recurrent'
            ].help_text = 'Readonly because this field is managed by Recurrent schedule'

            self.base_fields['metadata'].disabled = True
            self.base_fields['metadata'].help_text = 'Readonly for this type'

            if instance.metadata.get(MetadataFields.ORGANIZATION_ID.value):
                initial['organization'] = Organization.objects.get(
                    id=instance.metadata.get(MetadataFields.ORGANIZATION_ID.value)
                )
            if instance.metadata.get(MetadataFields.REQUIRED_EVIDENCE.value):
                initial['requires_evidence'] = (
                    True
                    if instance.metadata.get(MetadataFields.REQUIRED_EVIDENCE.value)
                    == 'Yes'
                    else False
                )
        super().__init__(*args, **kwargs)

    def save_m2m(self):
        self.save_linked_assignees()

        new_org = self.cleaned_data['organization']
        if new_org and self.instance.metadata.get(
            MetadataFields.ORGANIZATION_ID.value
        ) != str(new_org.id):
            self.instance.metadata[MetadataFields.ORGANIZATION_ID.value] = str(
                new_org.id
            )

        requires_evidence = 'Yes' if self.cleaned_data['requires_evidence'] else 'No'

        if (
            requires_evidence
            != self.instance.metadata[MetadataFields.REQUIRED_EVIDENCE.value]
        ):
            self.instance.metadata[
                MetadataFields.REQUIRED_EVIDENCE.value
            ] = requires_evidence

        self.instance.save()

    def save_linked_assignees(self):
        if not self.cleaned_data['assignees']:
            return

        cleaned_ids = self.cleaned_data['assignees'].values_list('id', flat=True)
        for assignee in self.initial['assignees']:
            if assignee not in cleaned_ids:
                self.instance.assignees.remove(assignee)

        existing_assignees = self.instance.assignees.all()
        for assignee in self.cleaned_data['assignees'].iterator():
            if assignee not in existing_assignees:
                self.instance.assignees.add(assignee)

    def save(self, *args, **kwargs):
        instance = super(ActionItemAdminForm, self).save()
        return instance


class ActionItemAdmin(VersionAdmin):
    formfield_overrides = {JSONField: {'widget': PrettyJSONWidget}}
    form = ActionItemAdminForm
    ordering = ('-id',)

    fieldsets = (
        (
            'General',
            {
                'fields': (
                    'name',
                    'description',
                    'status',
                    'parent_action_item',
                    'is_required',
                    'is_recurrent',
                    'recurrent_schedule',
                    'completion_date',
                    'due_date',
                    'display_id',
                )
            },
        ),
        ('Assignees', {'fields': ['assignees']}),
        ('Metadata', {'fields': ['metadata', 'organization', 'requires_evidence']}),
        ('Linked Data', {'fields': ['formatted_controls', 'formatted_frameworks']}),
    )

    list_display = (
        'reference_id',
        'type',
        'organization_link',
        'formatted_name',
        'formatted_description',
        'parent_action_item_link',
        'formatted_controls',
        'formatted_frameworks',
        'completion_date',
        'due_date',
        'is_required',
        'is_recurrent',
        'recurrent_schedule',
        'status',
        'requires_evidence',
        'display_id',
    )
    list_filter = (
        OrganizationFilter,
        ReferenceIdFilter,
        ControlsFilter,
        FrameworksFilter,
        NameFilter,
        EvidenceFilter,
        'status',
        'is_required',
        'is_recurrent',
        IsCustomFilter,
    )

    search_fields = ['name', 'metadata__referenceId']
    exclude = ['alerts', 'evidences']
    readonly_fields = [
        'parent_action_item',
        'formatted_controls',
        'formatted_frameworks',
    ]

    def organization_link(self, instance):
        organization_id = instance.metadata.get('organizationId')

        if organization_id:
            org = Organization.objects.filter(id=organization_id).first()
            url = f'/admin/organization/organization/{org.id}/change'
            return format_html('<a href="{}">{}</a>', url, org)
        return '-'

    organization_link.short_description = 'Organization'  # type: ignore

    def parent_action_item_link(self, instance):
        if instance.parent_action_item_id:
            try:
                item = ActionItem.objects.get(id=instance.parent_action_item_id)
                url = f'/admin/action_item/actionitem/{item.id}/change'
                return format_html(
                    '<div style="min-width: 250px;"> <a href="{}">{}</a></div>',
                    url,
                    item,
                )
            except Exception as e:
                logger.warning(f'Error getting parent action item: {e}')
                return 'Error :('
        return '-'

    parent_action_item_link.short_description = 'Parent'  # type: ignore

    def reference_id(self, instance):
        return instance.metadata.get('referenceId') or '[+]'

    reference_id.short_description = 'Reference ID'  # type: ignore

    def type(self, instance):
        return instance.metadata.get('type') or '--'

    type.short_description = 'Type'  # type: ignore

    def requires_evidence(self, instance):
        return instance.metadata.get('requiredEvidence')

    requires_evidence.short_description = 'Requires Evidence'  # type: ignore

    def formatted_name(self, instance):
        return format_html('<div style="min-width: 250px;">' + instance.name + '</div>')

    formatted_name.short_description = 'Name'  # type: ignore
    formatted_name.admin_order_field = 'name'  # type: ignore

    def formatted_description(self, instance):
        return format_html(
            '<div style="min-width: 500px;">' + instance.description + '</div>'
        )

    formatted_description.short_description = 'Description'  # type: ignore

    def formatted_frameworks(self, instance):
        ftags = []
        for ref_id in list(instance.controls.values_list('reference_id', flat=True)):
            tokens = ref_id.split('-')
            if len(tokens) == 3:
                ftags.append(ref_id.split('-')[2])

        if not ftags:
            return '-'

        certs = []
        for cert in Certification.objects.filter(code__in=ftags):
            div_start = SECTION_CHIP_DIV_START.format(random_color='#d0ecf0')
            url = f'/admin/control/control/{cert.id}/change'
            certs.append(
                ANCHOR + url + '">' + div_start + cert.name + CHIP_DIV_END + ANCHOR_END
            )

        if not len(certs):
            return '-'
        return format_html(TL_SECTION_START + ''.join(certs) + TL_SECTION_END)

    formatted_frameworks.short_description = 'Linked Frameworks'  # type: ignore
    formatted_frameworks.admin_order_field = 'controls'  # type: ignore

    def formatted_controls(self, instance):
        controls = []
        for control in instance.controls.iterator():
            div_start = SECTION_CHIP_DIV_START.format(random_color='#d0ecf0')
            url = f'/admin/control/control/{control.id}/change'
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


admin.site.register(ActionItem, ActionItemAdmin)
