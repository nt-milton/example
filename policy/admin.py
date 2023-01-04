from datetime import datetime, timedelta

from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db import models
from django.db.models import Q, QuerySet
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from django.db.models.functions import Cast
from django.forms import ModelForm, ModelMultipleChoiceField
from django.http import HttpRequest
from django.utils.html import format_html
from reversion.admin import VersionAdmin
from reversion.models import Version

from laika.utils.InputFilter import InputFilter
from organization.models import Organization
from tag.models import Tag
from user.admin import User

from .models import OnboardingPolicy, Policy, PolicyProxy, PublishedPolicy


def get_version_model_fields() -> Cast:
    return Cast(
        KeyTextTransform(
            'fields',
            Cast(
                KeyTransform(
                    '0', Cast('serialized_data', output_field=models.JSONField())
                ),
                output_field=models.JSONField(),
            ),
        ),
        output_field=models.JSONField(),
    )


class PublishedPolicyInlineAdmin(admin.TabularInline):
    model = PublishedPolicy
    list_display = ('version', 'created_at', 'published_by', 'comment')

    autocomplete_fields = ['published_by', 'owned_by', 'approved_by']
    extra = 1


class OrganizationFilter(InputFilter):
    parameter_name = 'organization'
    title = 'Organization Name'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(organization__name__icontains=self.value().strip())


class AdministratorFilter(InputFilter):
    parameter_name = 'administrator'
    title = 'Administrator'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                administrator_id__in=User.objects.filter(
                    Q(first_name__icontains=self.value().strip())
                    | Q(last_name__icontains=self.value().strip())
                ).values_list('id', flat=True)
            )


class OwnerFilter(InputFilter):
    parameter_name = 'owner'
    title = 'Owner'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                owner_id__in=User.objects.filter(
                    Q(first_name__icontains=self.value().strip())
                    | Q(last_name__icontains=self.value().strip())
                ).values_list('id', flat=True)
            )


class ApproverFilter(InputFilter):
    parameter_name = 'approver'
    title = 'Approver'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                approver_id__in=User.objects.filter(
                    Q(first_name__icontains=self.value().strip())
                    | Q(last_name__icontains=self.value().strip())
                ).values_list('id', flat=True)
            )


class CategoryFilter(InputFilter):
    parameter_name = 'category'
    title = 'Category'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(category__icontains=self.value().strip())


class PolicyForm(ModelForm):
    class Meta:
        model = Policy
        fields = [
            'id',
            'name',
            'organization',
            'policy_type',
            'control_family',
            'draft_key',
            'draft',
            'is_published',
            'is_visible_in_dataroom',
            'is_required',
            'is_draft_edited',
            'administrator',
            'approver',
            'owner',
            'category',
            'policy_text',
            'tags',
        ]

    tags = ModelMultipleChoiceField(
        required=False,
        queryset=Tag.objects.all(),
        widget=FilteredSelectMultiple('Tags', False, attrs={'rows': '10'}),
    )

    def __init__(self, *args, **kwargs):
        if 'instance' in kwargs and kwargs['instance']:
            instance = kwargs['instance']

            initial = kwargs.setdefault('initial', {})

            initial['tags'] = [tag.pk for tag in instance.tags.all().order_by('name')]

            self.base_fields['tags'].queryset = Tag.objects.filter(
                organization_id=instance.organization_id
            ).order_by('name')
        super(PolicyForm, self).__init__(*args, **kwargs)

    def save_m2m(self):
        for tag in self.cleaned_data['tags']:
            self.instance.tags.add(tag)

    def save(self, *args, **kwargs):
        instance = super(PolicyForm, self).save()
        self.save_m2m()
        return instance


class PolicyAdmin(VersionAdmin):
    model = Policy
    form = PolicyForm
    list_display = (
        'name',
        'organization',
        'is_published',
        'administrator',
        'approver',
        'owner',
        'category',
        'created_at',
        'updated_at',
    )
    list_filter = (
        OrganizationFilter,
        AdministratorFilter,
        OwnerFilter,
        ApproverFilter,
        CategoryFilter,
        'is_published',
    )
    autocomplete_fields = [
        'organization',
        'administrator',
        'approver',
        'owner',
        'action_items',
    ]

    readonly_fields = ['action_items']

    inlines = [PublishedPolicyInlineAdmin]


class OrganizationFilterForVersion(SimpleListFilter):
    title = 'Organization'
    parameter_name = 'organization'

    def lookups(self, request, model_admin):
        organizations = Organization.objects.all().order_by('-created_at')
        return [(c.id, c.name) for c in organizations]

    def queryset(self, request, queryset):
        if self.value():
            selected_ids = []
            for version in queryset:
                if (
                    version.field_dict.get('organization_id')
                    and str(version.field_dict.get('organization_id')) == self.value()
                ):
                    selected_ids.append(version.id)
            return queryset.filter(id__in=selected_ids)


class DeletedPolicyAdmin(VersionAdmin):
    def version_link(self, obj):
        url = f'/admin/policy/policy/recover/{obj.id}/'
        return format_html('<a href="{}">{}</a>', url, obj.id)

    version_link.short_description = 'Version Id'  # type: ignore

    list_display = (
        'version_link',
        'name',
        'organization',
        'policy_type',
        'created_at',
        'updated_at',
        'is_published',
        'owner',
    )
    list_filter = (
        'policy_type',
        'is_published',
        OrganizationFilterForVersion,
    )
    actions = None
    history_latest_first = True

    change_list_template = "admin/deleted_policy_change_list.html"

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        last_two_months = datetime.now() - timedelta(days=60)

        qs = self._reversion_order_version_queryset(
            Version.objects.get_deleted(self.model).filter(
                revision__date_created__gte=last_two_months
            )
        ).annotate(
            fields=get_version_model_fields(),
            name=Cast(KeyTextTransform('name', 'fields'), models.CharField()),
            created_at=Cast(
                KeyTextTransform('created_at', 'fields'), models.DateTimeField()
            ),
            updated_at=Cast(
                KeyTextTransform('updated_at', 'fields'), models.DateTimeField()
            ),
            policy_type=Cast(
                KeyTextTransform('policy_type', 'fields'), models.CharField()
            ),
            owner=Cast(KeyTextTransform('owner_id', 'fields'), models.CharField()),
            is_published=Cast(
                KeyTextTransform('is_published', 'fields'), models.BooleanField()
            ),
        )

        return qs

    def is_published(self, instance):
        return instance.field_dict.get('is_published')

    is_published.boolean = True  # type: ignore

    def organization(self, instance):
        org = Organization.objects.filter(
            id=instance.field_dict.get('organization_id')
        ).first()

        return org.name if org else '-'

    def owner(self, instance):
        return User.objects.filter(id=instance.field_dict.get('owner_id')).first()

    owner.admin_order_field = 'owner'  # type: ignore


admin.site.register(Policy, PolicyAdmin)
admin.site.register(PolicyProxy, DeletedPolicyAdmin)


class OnboardingPolicyAdmin(VersionAdmin):
    model = OnboardingPolicy
    list_display = ('description', 'organization', 'use_laika_template', 'file')
    list_filter = ('organization',)


admin.site.register(OnboardingPolicy, OnboardingPolicyAdmin)
