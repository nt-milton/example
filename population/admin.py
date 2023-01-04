from django.contrib import admin
from reversion.admin import VersionAdmin

from fieldwork.models import Evidence
from fieldwork.utils import get_display_id_order_annotation

from .models import (
    AuditPopulation,
    AuditPopulationEvidence,
    AuditPopulationSample,
    Sample,
)


class EvidenceInlineAdmin(admin.StackedInline):
    model = AuditPopulationEvidence

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'evidence_request':
            population_id = request.resolver_match.kwargs.get('object_id')
            population = AuditPopulation.objects.get(id=population_id)
            kwargs["queryset"] = (
                Evidence.objects.filter(audit_id=population.audit.id)
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


class SampleInlineAdmin(admin.StackedInline):
    model = AuditPopulationSample


class AuditPopulationAdmin(VersionAdmin):
    model = AuditPopulation

    list_display = (
        'display_id',
        'name',
        'audit',
        'status',
        'pop_type',
        'status',
        'created_at',
        'updated_at',
    )

    list_filter = ('audit',)
    inlines = [EvidenceInlineAdmin, SampleInlineAdmin]

    readonly_fields = ['times_moved_back_to_open']


admin.site.register(AuditPopulation, AuditPopulationAdmin)


class SampleAdmin(VersionAdmin):
    model = Sample

    list_display = ['id', 'name', 'evidence_request']


admin.site.register(Sample, SampleAdmin)
