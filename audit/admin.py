from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from reversion.admin import VersionAdmin

from feature.models import AuditorFlag
from user.models import Auditor

from .constants import AUDIT_FRAMEWORK_TYPES
from .models import (
    Audit,
    AuditAuditor,
    AuditFeedbackReason,
    AuditFirm,
    AuditFrameworkType,
    AuditReportSection,
    AuditStatus,
    FrameworkReportTemplate,
    UnlockedAuditFrameworkTypeOrganization,
)
from .utils.admin import update_status_checkboxes


class AuditReportSectionInlineAdmin(admin.StackedInline):
    verbose_name = 'Section'
    verbose_name_plural = 'Report Sections'

    model = AuditReportSection
    fields = ('name', 'file', 'section')


class FrameworkReportTemplateInlineAdmin(admin.StackedInline):
    verbose_name = 'Section'
    verbose_name_plural = 'Report Templates'

    model = FrameworkReportTemplate
    fields = ('name', 'file', 'section')


class AuditStatusInlineAdmin(admin.StackedInline):
    model = AuditStatus
    fieldsets = (
        (
            'Auditor request stage',
            {
                'fields': (
                    'requested',
                    'confirm_audit_details',
                    'engagement_letter_link',
                    'engagement_letter_url',
                    'control_design_assessment_link',
                    'control_design_assessment_url',
                    'kickoff_meeting_link',
                )
            },
        ),
        (
            'Auditor initiated stage',
            {
                'fields': (
                    'initiated',
                    'confirm_engagement_letter_signed',
                    'confirm_control_design_assessment',
                    'confirm_kickoff_meeting',
                )
            },
        ),
        (
            'Auditor fieldwork stage',
            {
                'fields': (
                    'fieldwork',
                    'complete_fieldwork',
                    'representation_letter_link',
                    'representation_letter_url',
                    'management_assertion_link',
                    'management_assertion_url',
                    'subsequent_events_questionnaire_link',
                    'subsequent_events_url',
                    'draft_report_file_generated',
                    'draft_report_name',
                    'draft_report',
                )
            },
        ),
        (
            'Auditor draft report stage',
            {
                'fields': (
                    'in_draft_report',
                    'confirm_completion_of_signed_documents',
                    'final_report',
                    'first_draft_report_generated_timestamp',
                    'draft_report_approved',
                    'draft_report_approved_timestamp',
                    'draft_report_approved_by',
                )
            },
        ),
        ('Auditor completed stage', {'fields': ('completed',)}),
    )
    readonly_fields = [
        'engagement_letter_url',
        'representation_letter_url',
        'management_assertion_url',
        'subsequent_events_url',
        'control_design_assessment_url',
    ]

    max_num = 1

    def requested(self, instance):
        return instance.requested

    def confirm_audit_details(self, instance):
        return instance.confirm_audit_details

    def engagement_letter_link(self, instance):
        return instance.engagement_letter_link

    def engagement_letter_url(self, instance):
        return instance.engagement_letter_url

    def representation_letter_url(self, instance):
        return instance.representation_letter_url

    def management_assertion_url(self, instance):
        return instance.management_assertion_url

    def subsequent_events_url(self, instance):
        return instance.subsequent_events_url

    def control_design_assessment_link(self, instance):
        return instance.control_design_assessment_link

    def kickoff_meeting_link(self, instance):
        return instance.kickoff_meeting_link

    def initiated(self, instance):
        return instance.initiated

    def confirm_engagement_letter_signed(self, instance):
        return instance.confirm_engagement_letter_signed

    def confirm_control_design_assessment(self, instance):
        return instance.confirm_control_design_assessment

    def confirm_kickoff_meeting(self, instance):
        return instance.confirm_kickoff_meeting

    def fieldwork(self, instance):
        return instance.fieldwork

    def representation_letter_link(self, instance):
        return instance.representation_letter_link

    def management_assertion_link(self, instance):
        return instance.management_assertion_link

    def subsequent_events_questionnaire_link(self, instance):
        return instance.subsequent_events_questionnaire_link

    def draft_report(self, instance):
        return instance.draft_report

    def in_draft_report(self, instance):
        return instance.in_draft_report

    def confirm_completion_of_signed_documents(self, instance):
        return instance.confirm_completion_of_signed_documents

    def final_report(self, instance):
        return instance.final_report

    def completed(self, instance):
        return instance.completed


class AuditorFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _('Auditor')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'auditor'

    def lookups(self, request, model_admin):
        users = set([a.auditor.user for a in model_admin.model.objects.all()])
        return [(u.id, u.first_name + u.last_name) for u in users if u is not None]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(auditor__is_staff=True, auditor__id=self.value())
        return queryset.all()


class AuditAuditorAdmin(VersionAdmin):
    model = AuditAuditor

    list_display = ('auditor', 'audit', 'title_role')
    list_filter = ('auditor', 'audit')
    ordering = ('auditor',)


class AuditAuditorInlineAdmin(admin.StackedInline):
    model = AuditAuditor
    verbose_name = 'Auditor Assigned'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'auditor':
            audit_id = request.resolver_match.kwargs.get('object_id')
            audit = Audit.objects.get(id=audit_id)
            kwargs["queryset"] = Auditor.objects.filter(
                audit_firms__in=[audit.audit_firm]
            ).order_by('user')

            return super(AuditAuditorInlineAdmin, self).formfield_for_foreignkey(
                db_field, request, **kwargs
            )

        return db_field.formfield(**kwargs)


class AuditFrameworkTypeInlineAdmin(admin.StackedInline):
    model = AuditFrameworkType
    list_display = ('audit_type',)

    def audit_type(self, obj):
        audit_framework_type_keys = dict(AUDIT_FRAMEWORK_TYPES)
        return audit_framework_type_keys[obj.audit_type]


class AuditAdmin(VersionAdmin):
    model = Audit
    list_display = (
        'name',
        'organization',
        'audit_framework',
        'audit_configuration',
        'completed_at',
        'report',
        'created_at',
        'updated_at',
    )
    list_filter = ('audit_firm',)
    ordering = ('-created_at',)
    readonly_fields = ('audit_type',)

    inlines = [
        AuditAuditorInlineAdmin,
        AuditStatusInlineAdmin,
        AuditReportSectionInlineAdmin,
    ]

    fieldsets = (
        (
            "Audit Information",
            {
                "description": "Audit Information",
                "fields": (
                    'organization',
                    'name',
                    'audit_firm',
                    'completed_at',
                    'report',
                    'auto_fetch_executed',
                    'is_demo',
                    'exported_audit_file',
                    'use_new_version',
                ),
            },
        ),
        (
            'Audit Type Information',
            {
                'description': 'Information related to audit type',
                'fields': ('audit_type', 'audit_framework_type', 'audit_configuration'),
            },
        ),
    )

    def save_formset(self, request, form, formset, change):
        formset.save()
        status = formset.forms[0].instance
        if isinstance(status, AuditStatus):
            update_status_checkboxes(status)
            status.save()

    def get_actions(self, request) -> list[str]:
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def has_delete_permission(self, request, obj=None) -> bool:
        return obj.is_demo if obj else False

    def audit_framework(self, obj):
        audit_framework_type_keys = dict(AUDIT_FRAMEWORK_TYPES)
        return audit_framework_type_keys[obj.audit_framework_type.audit_type]

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        audit_id = request.resolver_match.kwargs.get('object_id')
        audit = Audit.objects.get(id=audit_id)
        if db_field.name == "audit_framework_type":
            kwargs["queryset"] = AuditFrameworkType.objects.filter(
                id__in=UnlockedAuditFrameworkTypeOrganization.objects.filter(
                    organization=audit.organization
                )
                .values_list('audit_framework_type', flat=True)
                .distinct()
            )

        return super(AuditAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )


class FeatureFlagInlineAdmin(admin.StackedInline):
    model = AuditorFlag


class AuditFirmAdmin(admin.ModelAdmin):
    model = AuditFirm

    list_display = ('name',)

    inlines = [FeatureFlagInlineAdmin]


class UnlockedAuditFrameworkTypeOrganizationInlineAdmin(admin.StackedInline):
    model = UnlockedAuditFrameworkTypeOrganization


class AuditFeedbackReasonInlineAdmin(admin.StackedInline):
    verbose_name = 'Feedback Reason'
    verbose_name_plural = 'Feedback Reason'

    model = AuditFeedbackReason
    fields = ('reason',)


class AuditFrameworkTypeAdmin(admin.ModelAdmin):
    model = AuditFrameworkType
    list_display = ('audit_type',)
    inlines = [
        UnlockedAuditFrameworkTypeOrganizationInlineAdmin,
        FrameworkReportTemplateInlineAdmin,
        AuditFeedbackReasonInlineAdmin,
    ]

    def audit_type(self, obj):
        audit_framework_type_keys = dict(AUDIT_FRAMEWORK_TYPES)
        return audit_framework_type_keys[obj.audit_type]


admin.site.register(AuditFirm, AuditFirmAdmin)
admin.site.register(Audit, AuditAdmin)
admin.site.register(AuditAuditor, AuditAuditorAdmin)
admin.site.register(AuditFrameworkType, AuditFrameworkTypeAdmin)
