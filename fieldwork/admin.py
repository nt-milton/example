from django.contrib import admin
from reversion.admin import VersionAdmin

from audit.models import Audit
from fieldwork.utils import get_display_id_order_annotation
from user.models import Auditor

from .models import (
    Attachment,
    AttachmentSourceType,
    Criteria,
    CriteriaAuditType,
    CriteriaRequirement,
    Evidence,
    EvidenceFetchLogic,
    EvidenceMetric,
    EvidenceStatusTransition,
    FetchLogic,
    Requirement,
    RequirementEvidence,
    Test,
)


class EvidenceFetchLogicInlineAdmin(admin.StackedInline):
    model = EvidenceFetchLogic

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'evidence':
            fetch_logic_id = request.resolver_match.kwargs.get('object_id')
            fetch_logic = FetchLogic.objects.get(id=fetch_logic_id)
            kwargs["queryset"] = (
                Evidence.objects.filter(audit=fetch_logic.audit)
                .annotate(
                    display_id_sort=get_display_id_order_annotation(
                        preffix='ER-', field='display_id'
                    )
                )
                .order_by('display_id_sort')
            )
            return super(EvidenceFetchLogicInlineAdmin, self).formfield_for_foreignkey(
                db_field, request, **kwargs
            )

        return db_field.formfield(**kwargs)


class FetchLogicEvidenceInlineAdmin(admin.StackedInline):
    model = EvidenceFetchLogic

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'fetch_logic':
            evidence_id = request.resolver_match.kwargs.get('object_id')
            evidence = Evidence.objects.get(id=evidence_id)
            kwargs["queryset"] = (
                FetchLogic.objects.filter(audit_id=evidence.audit.id)
                .annotate(
                    display_id_sort=get_display_id_order_annotation(
                        preffix='FL-', field='code'
                    )
                )
                .order_by('display_id_sort')
            )
            return super(FetchLogicEvidenceInlineAdmin, self).formfield_for_foreignkey(
                db_field, request, **kwargs
            )

        return db_field.formfield(**kwargs)


class AttachmentInlineAdmin(admin.StackedInline):
    model = Attachment


class MetricsInlineAdmin(admin.StackedInline):
    model = EvidenceMetric

    min_num = 1
    extra = 0


class StatusTransitionInlineAdmin(admin.StackedInline):
    model = EvidenceStatusTransition
    classes = ['collapse']

    min_num = 1
    extra = 0


class EvidenceAdmin(VersionAdmin):
    model = Evidence
    list_display = (
        'display_id',
        'name',
        'audit',
        'status',
        'assignee',
        'read',
        'created_at',
        'updated_at',
    )
    list_filter = ('audit',)
    inlines = [
        FetchLogicEvidenceInlineAdmin,
        AttachmentInlineAdmin,
        StatusTransitionInlineAdmin,
        MetricsInlineAdmin,
    ]

    readonly_fields = ['times_moved_back_to_open']


admin.site.register(Evidence, EvidenceAdmin)


class EvidenceInlineAdmin(admin.StackedInline):
    model = RequirementEvidence

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'evidence':
            requirement_id = request.resolver_match.kwargs.get('object_id')
            requirement = Requirement.objects.get(id=requirement_id)
            kwargs["queryset"] = (
                Evidence.objects.filter(audit_id=requirement.audit.id)
                .annotate(
                    display_id_sort=get_display_id_order_annotation(
                        preffix='ER-', field='display_id'
                    )
                )
                .order_by('display_id_sort')
            )
            return super(EvidenceInlineAdmin, self).formfield_for_foreignkey(
                db_field, request, **kwargs
            )

        return db_field.formfield(**kwargs)


class CriteriaInlineAdmin(admin.StackedInline):
    model = CriteriaRequirement


class RequirementAdmin(VersionAdmin):
    model = Requirement
    list_display = (
        'display_id',
        'name',
        'status',
        'audit',
        'tester',
        'tester_updated_at',
        'reviewer',
        'reviewer_updated_at',
        'result',
        'created_at',
        'updated_at',
    )
    list_filter = ('audit',)
    inlines = [
        EvidenceInlineAdmin,
        CriteriaInlineAdmin,
    ]

    readonly_fields = ['times_moved_back_to_open']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'tester' or db_field.name == 'reviewer':
            requirement_id = request.resolver_match.kwargs.get('object_id')
            requirement = Requirement.objects.get(id=requirement_id)
            kwargs["queryset"] = Auditor.objects.filter(
                audit_firms__in=[requirement.audit.audit_firm]
            ).order_by('user')

            return super(RequirementAdmin, self).formfield_for_foreignkey(
                db_field, request, **kwargs
            )

        return db_field.formfield(**kwargs)


admin.site.register(Requirement, RequirementAdmin)


class CriteriaTypeInlineAdmin(admin.StackedInline):
    model = CriteriaAuditType


class RequirementInlineAdmin(admin.StackedInline):
    model = CriteriaRequirement


class CriteriaAdmin(VersionAdmin):
    model = Criteria
    list_display = ('display_id', 'audit', 'description', 'created_at', 'updated_at')
    list_filter = (
        'audit',
        'display_id',
    )
    inlines = [
        CriteriaTypeInlineAdmin,
        RequirementInlineAdmin,
    ]


admin.site.register(Criteria, CriteriaAdmin)


class FetchLogicAdmin(VersionAdmin):
    model = FetchLogic
    list_display = ('code', 'type', 'logic', 'created_at', 'updated_at')
    list_filter = ('audit',)
    inlines = [
        EvidenceFetchLogicInlineAdmin,
    ]


admin.site.register(FetchLogic, FetchLogicAdmin)


class AuditFilter(admin.SimpleListFilter):
    title = 'Audit'
    parameter_name = 'audit'

    def lookups(self, request, model_admin):
        audits = Audit.objects.order_by('name')
        return [(audit.id, audit.name) for audit in audits]

    def queryset(self, request, queryset):
        if self.value():
            return (
                queryset.filter(requirement__audit_id__exact=self.value())
                .annotate(
                    display_id_sort=get_display_id_order_annotation(
                        preffix='Test-', field='display_id'
                    )
                )
                .order_by('display_id_sort')
            )


class TestAdmin(VersionAdmin):
    model = Test
    list_display = ('display_id', 'name', 'result', 'notes', 'created_at', 'updated_at')
    list_filter = (AuditFilter,)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'requirement':
            test_id = request.resolver_match.kwargs.get('object_id')
            test = Test.objects.get(id=test_id)
            kwargs["queryset"] = (
                Requirement.objects.filter(audit=test.requirement.audit)
                .annotate(
                    display_id_sort=get_display_id_order_annotation(
                        preffix='LCL-', field='display_id'
                    )
                )
                .order_by('display_id_sort')
            )

            return super(TestAdmin, self).formfield_for_foreignkey(
                db_field, request, **kwargs
            )

        return db_field.formfield(**kwargs)


admin.site.register(Test, TestAdmin)


class AttachmentSourceTypeAdmin(VersionAdmin):
    model = AttachmentSourceType
    list_display = ('name',)
    readonly_fields = ('name',)
    fieldsets = (
        (
            None,
            {
                'fields': (
                    'name',
                    'template',
                )
            },
        ),
    )


admin.site.register(AttachmentSourceType, AttachmentSourceTypeAdmin)
