from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import ValidationError
from django.forms import ModelForm

from certification.models import Certification
from monitor.constants import SOURCE_SYSTEM_CHOICES
from monitor.models import MonitorHealthCondition, MonitorType, OrganizationMonitor
from monitor.sqlutils import compatible_queries
from monitor.validators import (
    validate_exclude_field,
    validate_fix_me_link,
    validate_subtask_reference,
)
from organization.models import Organization


class SendDryRunRequest(forms.Form):
    organization = forms.ModelChoiceField(queryset=Organization.objects.all())
    query = forms.CharField(widget=forms.Textarea(attrs={'rows': 10, 'cols': 40}))
    validation_query = forms.CharField(
        required=False, widget=forms.Textarea(attrs={'rows': 10, 'cols': 40})
    )
    health_condition = forms.ChoiceField(choices=MonitorHealthCondition.choices)

    def __init__(self, *args, **kwargs):
        super(SendDryRunRequest, self).__init__(*args, **kwargs)


class DuplicateMonitorForm(forms.Form):
    organization = forms.ModelChoiceField(queryset=Organization.objects.all())
    monitor = forms.CharField(widget=forms.HiddenInput())
    name = forms.CharField()
    query = forms.CharField(widget=forms.Textarea(attrs={'rows': 10, 'cols': 40}))
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 10, 'cols': 40}))

    def __init__(self, *args, **kwargs):
        super(DuplicateMonitorForm, self).__init__(*args, **kwargs)


class MonitorAdminForm(ModelForm):
    sources = forms.MultipleChoiceField(
        choices=SOURCE_SYSTEM_CHOICES,
        widget=FilteredSelectMultiple(
            'Source Systems',
            False,
        ),
        required=False,
    )
    source_systems = forms.CharField(widget=forms.HiddenInput(), required=False)

    frameworks = forms.ModelMultipleChoiceField(
        queryset=Certification.objects.all(),
        widget=FilteredSelectMultiple(
            'Frameworks',
            False,
        ),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super(MonitorAdminForm, self).__init__(*args, **kwargs)
        self.initial['sources'] = self.initial.get('source_systems')

    def clean_query(self):
        query = self.cleaned_data['query']
        organization_monitors = OrganizationMonitor.objects.filter(
            monitor=self.instance,
        ).exclude(query='')
        for organization_monitor in organization_monitors:
            if not compatible_queries(query, organization_monitor.query):
                raise ValidationError(
                    'Query does not match query for organization monitor in '
                    f'organization: {organization_monitor.organization}'
                )
        return query

    def clean_fix_me_link(self):
        fix_me_link = self.cleaned_data['fix_me_link']
        validate_fix_me_link(fix_me_link, self.data['query'])
        return fix_me_link

    def clean_exclude_field(self):
        exclude_field = self.cleaned_data['exclude_field']
        validate_exclude_field(exclude_field, self.data['query'])
        return exclude_field

    def clean_subtask_reference(self):
        subtask_reference = self.data['subtask_reference']
        monitor_type = self.data['monitor_type']
        validate_subtask_reference(subtask_reference, monitor_type)
        return subtask_reference

    def clean_source_systems(self):
        return self.data.getlist('sources')


class OrganizationMonitorAdminForm(ModelForm):
    def clean_query(self):
        query = self.cleaned_data['query']
        monitor = self.cleaned_data['monitor']
        if (
            query
            and monitor.monitor_type == MonitorType.SYSTEM
            and not compatible_queries(query, monitor.query)
        ):
            raise ValidationError('Query does not match monitor query')
        return query
