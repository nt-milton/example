from multiprocessing.pool import ThreadPool

from django.contrib import admin, messages
from django.core.handlers.asgi import ASGIRequest
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import path
from django.utils.html import format_html
from django.views.decorators.http import require_GET
from reversion.admin import VersionAdmin

from audit.models import OrganizationAuditFirm
from audit.utils.tags import (
    link_audit_tags_to_action_items_evidence,
    link_subtasks_evidence_to_tags,
)
from feature.models import Flag
from laika.utils.InputFilter import InputFilter
from report.models import Template
from user.constants import CONCIERGE
from user.models import User

from .constants import compliance_architect_user, customer_success_manager_user
from .models import (
    OffboardingVendor,
    Onboarding,
    OnboardingSetupStep,
    Organization,
    OrganizationChecklist,
    OrganizationChecklistRun,
    OrganizationChecklistRunSteps,
)
from .mutations import update_ca_user, update_csm_user
from .tasks import (
    create_organization_seed,
    create_super_admin_users,
    delete_aws_data,
    delete_organization_data,
    delete_users_from_idp,
    tddq_execution,
)

pool = ThreadPool()


class FeatureFlagInlineAdmin(admin.StackedInline):
    model = Flag
    extra = 1


class TemplatesInlineAdmin(admin.StackedInline):
    model = Template
    extra = 1


class OrganizationAuditFirmInlineAdmin(admin.StackedInline):
    model = OrganizationAuditFirm
    extra = 1


class IdFilter(InputFilter):
    parameter_name = 'id'
    title = 'Organization ID'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(id=self.value().strip())


class NameFilter(InputFilter):
    parameter_name = 'name'
    title = 'Organization Name'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(name__icontains=self.value().strip())


class StateFilter(InputFilter):
    parameter_name = 'state'
    title = 'State'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(state__icontains=self.value().strip())


class CreatedByFilter(InputFilter):
    parameter_name = 'created_by'
    title = 'Created by'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                created_by_id__in=User.objects.filter(
                    Q(first_name__icontains=self.value().strip())
                    | Q(last_name__icontains=self.value().strip())
                ).values_list('id', flat=True)
            )


class FlagsFilter(InputFilter):
    parameter_name = 'feature_flag'
    title = 'Features'
    description = 'A space separated values'

    def queryset(self, request, queryset):
        if self.value():
            filter_query = Q()
            for item in self.value().strip().split(' '):
                filter_query.add(Q(feature_flags__name__icontains=item), Q.OR)
            return queryset.filter(filter_query)


class OrganizationAdmin(VersionAdmin):
    model = Organization
    ordering = ('-created_at',)

    def created_by_user_link(self, obj):
        cb = obj.created_by
        if cb:
            url = f'/admin/user/user/{cb.id}/change'
            return format_html('<a href="{}">{}</a>', url, cb)
        return 'Not assigned'

    created_by_user_link.short_description = "Created By"  # type: ignore

    def csm_link(self, obj):
        csm = obj.customer_success_manager_user
        if csm:
            url = f'/admin/user/user/{csm.id}/change'
            return format_html('<a href="{}">{}</a>', url, csm)
        return 'Not assigned'

    csm_link.short_description = "CSM"  # type: ignore

    def ca_link(self, obj):
        ca = obj.compliance_architect_user
        if ca:
            url = f'/admin/user/user/{ca.id}/change'
            return format_html('<a href="{}">{}</a>', url, ca)
        return 'Not assigned'

    ca_link.short_description = "CSM"  # type: ignore

    list_display = (
        'id',
        'name',
        'state',
        'is_internal',
        'csm_link',
        'ca_link',
        'created_by_user_link',
        'created_at',
        'features',
    )

    search_fields = ('name',)

    autocomplete_fields = ['created_by']

    list_filter = (
        IdFilter,
        NameFilter,
        StateFilter,
        CreatedByFilter,
        FlagsFilter,
        'is_internal',
        'created_at',
    )
    inlines = [
        FeatureFlagInlineAdmin,
        TemplatesInlineAdmin,
        OrganizationAuditFirmInlineAdmin,
    ]

    actions = ['tag_subtasks_evidence', 'tag_action_item_evidence', 'tddq_sync']
    change_form_template = 'admin/organization_change_form.html'
    change_list_template = "admin/organization_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('sync_all_tddq/', sync_all_tddq),
        ]
        return custom_urls + urls

    def tddq_sync(self, request, queryset):
        messages.info(request, 'TDDQ Sync is happening in the background')

        organization_ids = list(queryset.values_list('id', flat=True))
        formula = (
            '('
            + ', '.join(
                [f'{"{Organization ID}"} = "{org_id}"' for org_id in organization_ids]
            )
            + ')'
        )
        formula = 'OR' + formula if len(organization_ids) else formula
        tddq_execution.delay(formula)

    tddq_sync.short_description = 'TDDQ Airtable Sync'  # type: ignore

    def features(self, instance):
        flags = []
        for flag in instance.feature_flags.iterator():
            if flag.is_enabled and flag.name not in flags:
                flags.append(flag.name)
        return flags

    features.short_description = 'Features'  # type: ignore

    def has_delete_permission(self, request, obj=None):
        return False

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_delete'] = (
            request.user.is_active and request.user.is_superuser
        )
        return super(OrganizationAdmin, self).changeform_view(
            request, object_id, form_url, extra_context
        )

    def response_change(self, request, obj):
        if '_delete_organization' in request.POST:
            delete_users_from_idp(obj)
            delete_aws_data.delay(obj.id)
            messages.info(
                request, 'Delete Organization data is running in the background'
            )

            pool.apply_async(
                delete_organization_data,
                args=(
                    obj,
                    request.user,
                ),
            )
            return HttpResponseRedirect("/admin/organization/organization")
        return super().response_change(request, obj)

    def tag_subtasks_evidence(self, request, queryset):
        for organization in queryset:
            link_subtasks_evidence_to_tags(organization.id)

    tag_subtasks_evidence.short_description = 'Tag subtasks evidence'  # type: ignore

    def tag_action_item_evidence(self, request, queryset):
        for organization in queryset:
            link_audit_tags_to_action_items_evidence(organization)

    tag_action_item_evidence.short_description = (  # type: ignore
        'Tag action items evidence'
    )

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        if db_field.name == "customer_success_manager_user":
            kwargs["queryset"] = User.objects.filter(role=CONCIERGE)
        elif db_field.name == "compliance_architect_user":
            kwargs["queryset"] = User.objects.filter(role=CONCIERGE)

        return super(OrganizationAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
            super().save_model(request, obj, form, change)
            create_super_admin_users(obj)
            create_organization_seed(obj, request.user)

        if form.changed_data and compliance_architect_user in form.changed_data:
            initial_org = Organization.objects.get(id=obj.id)
            ca = form.cleaned_data.get(compliance_architect_user)
            update_ca_user(initial_org, {compliance_architect_user: ca})

        if form.changed_data and customer_success_manager_user in form.changed_data:
            initial_org = Organization.objects.get(id=obj.id)
            csm = form.cleaned_data.get(customer_success_manager_user)
            update_csm_user(initial_org, {customer_success_manager_user: csm})

        super().save_model(request, obj, form, change)


@require_GET
def sync_all_tddq(request: ASGIRequest):
    messages.info(request, 'Sync is running in the background')
    tddq_execution.delay('')
    return HttpResponseRedirect('../')


class OnboardingSetupStepInlineAdmin(admin.TabularInline):
    model = OnboardingSetupStep
    fields = ('completed',)

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class OnboardingAdmin(VersionAdmin):
    model = Onboarding

    fields = ('organization', 'state', 'period_ends')
    list_display = ('organization', 'state', 'period_ends')
    inlines = [
        OnboardingSetupStepInlineAdmin,
    ]
    readonly_fields = ['organization', 'state']


class OrganizationChecklistAdmin(VersionAdmin):
    model = OrganizationChecklist
    autocomplete_fields = ('action_item', 'organization')


class OrganizationChecklistRunAdmin(VersionAdmin):
    model = OrganizationChecklistRun
    list_display = ('owner', 'date')
    autocomplete_fields = ('owner',)


class OffboardingVendorAdmin(VersionAdmin):
    model = OffboardingVendor
    list_display = (
        'checklist_run',
        'vendor',
        'date',
        'status',
    )


class OffboardingStepsAdmin(VersionAdmin):
    model = OrganizationChecklistRunSteps
    list_display = (
        'checklist_run',
        'date',
        'status',
    )


admin.site.register(Organization, OrganizationAdmin)
admin.site.register(Onboarding, OnboardingAdmin)
admin.site.register(OrganizationChecklist, OrganizationChecklistAdmin)
admin.site.register(OrganizationChecklistRun, OrganizationChecklistRunAdmin)
admin.site.register(OffboardingVendor, OffboardingVendorAdmin)
admin.site.register(OrganizationChecklistRunSteps, OffboardingStepsAdmin)
