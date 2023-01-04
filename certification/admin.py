from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.forms import ModelForm, ModelMultipleChoiceField
from reversion.admin import VersionAdmin

from laika.utils.InputFilter import InputFilter
from organization.models import Organization

from .models import (
    ArchivedUnlockedOrganizationCertification,
    Certification,
    CertificationSection,
    UnlockedOrganizationCertification,
)

archived_playbooks_unlocked_organizations = 'archived_playbooks_unlocked_organizations'


class NameFilter(InputFilter):
    parameter_name = 'name'
    title = 'Name'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(name__icontains=self.value().strip())


class CodeFilter(InputFilter):
    parameter_name = 'code'
    title = 'Code'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(code__icontains=self.value().strip())


class UnlockedOrganizationFilter(InputFilter):
    parameter_name = 'unlockedOrganization'
    title = 'Unlocked Organization'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                id__in=UnlockedOrganizationCertification.objects.filter(
                    organization__name__icontains=self.value().strip()
                ).values_list('certification_id', flat=True)
            )


class ArchivedUnlockedOrganizationFilter(InputFilter):
    parameter_name = 'archivedUnlockedOrganization'
    title = 'Archived Playbooks Unlocked Organization'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                id__in=ArchivedUnlockedOrganizationCertification.objects.filter(
                    organization__name__icontains=self.value().strip()
                ).values_list('certification_id', flat=True)
            )


class CertificationForm(ModelForm):
    class Meta:
        model = Certification
        fields = [
            'name',
            'code',
            'is_visible',
            'sort_index',
            'airtable_record_id',
            'description',
            'logo',
            'regex',
            'required_action_items',
        ]

    unlocked_organizations = ModelMultipleChoiceField(
        required=False,
        queryset=Organization.objects.exclude(
            name='My Compliance Organizations Upsert'
        ).order_by('name'),
        widget=FilteredSelectMultiple('Organizations', False, attrs={'rows': '10'}),
    )

    archived_playbooks_unlocked_organizations = ModelMultipleChoiceField(
        required=False,
        queryset=Organization.objects.exclude(
            name='My Compliance Organizations Upsert'
        ).order_by('name'),
        widget=FilteredSelectMultiple('Organizations', False, attrs={'rows': '10'}),
    )

    def __init__(self, *args, **kwargs):
        if 'instance' in kwargs and kwargs['instance']:
            initial = kwargs.setdefault('initial', {})
            instance = kwargs['instance']

            initial['unlocked_organizations'] = [
                obj.organization_id
                for obj in UnlockedOrganizationCertification.objects.filter(
                    certification_id=instance.id
                )
            ]

            initial[archived_playbooks_unlocked_organizations] = [
                obj.organization_id
                for obj in ArchivedUnlockedOrganizationCertification.objects.filter(
                    certification_id=instance.id
                )
            ]
        super(CertificationForm, self).__init__(*args, **kwargs)

    def save_unlocked_organizations(self):
        cleaned_ids = self.cleaned_data['unlocked_organizations'].values_list(
            'id', flat=True
        )
        for org in self.initial['unlocked_organizations']:
            if org not in cleaned_ids:
                UnlockedOrganizationCertification.objects.filter(
                    organization_id=org, certification_id=self.instance.id
                ).delete()

        for org in self.cleaned_data['unlocked_organizations']:
            if not UnlockedOrganizationCertification.objects.filter(
                organization_id=org.id, certification_id=self.instance.id
            ).exists():
                UnlockedOrganizationCertification.objects.create(
                    organization_id=org.id, certification_id=self.instance.id
                )

    def save_archived_unlocked_organizations(self):
        cleaned_ids = self.cleaned_data[
            'archived_playbooks_unlocked_organizations'
        ].values_list('id', flat=True)

        for org in self.initial['archived_playbooks_unlocked_organizations']:
            if org not in cleaned_ids:
                ArchivedUnlockedOrganizationCertification.objects.filter(
                    organization_id=org, certification_id=self.instance.id
                ).delete()

        for org in self.cleaned_data['archived_playbooks_unlocked_organizations']:
            if not ArchivedUnlockedOrganizationCertification.objects.filter(
                organization_id=org.id, certification_id=self.instance.id
            ).exists():
                ArchivedUnlockedOrganizationCertification.objects.create(
                    organization_id=org.id, certification_id=self.instance.id
                )

    def save_m2m(self):
        self.save_unlocked_organizations()
        self.save_archived_unlocked_organizations()

    def save(self, *args, **kwargs):
        instance = super(CertificationForm, self).save()
        return instance


class CertificationAdmin(VersionAdmin):
    model = Certification
    form = CertificationForm
    ordering = ('sort_index',)

    list_display = (
        'name',
        'code',
        'is_visible',
        'sort_index',
        'airtable_record_id',
        'description',
        'logo',
        'regex',
        'updated_at',
    )

    search_fields = ('name',)
    list_filter = (
        NameFilter,
        CodeFilter,
        UnlockedOrganizationFilter,
        ArchivedUnlockedOrganizationFilter,
        'is_visible',
    )


admin.site.register(Certification, CertificationAdmin)


class CertificationSectionAdmin(VersionAdmin):
    list_display = ('name', 'certification', 'created_at')
    list_filter = ('certification',)

    def certification(self, instance):
        return instance.certification.name


admin.site.register(CertificationSection, CertificationSectionAdmin)
