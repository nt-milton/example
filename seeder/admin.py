from multiprocessing.pool import ThreadPool

from django.contrib import admin
from django.db.models.signals import post_save
from django.utils import timezone
from reversion.admin import VersionAdmin

from feature.constants import new_controls_feature_flag
from organization.models import Onboarding, Organization, OrganizationChecklistRun
from organization.signals import (
    execute_post_onboarding_actions,
    execute_pre_offboarding_actions,
)

from .constants import (
    ALL_MY_COMPLIANCE_ORG_FAKE_SFDC_ID,
    ALL_MY_COMPLIANCE_ORG_FAKE_WEBSITE,
    ALL_MY_COMPLIANCE_ORGS,
)
from .models import MyComplianceMigration, Seed, SeedProfile

pool = ThreadPool()


def disconnect_org_post_savings():
    post_save.disconnect(
        execute_post_onboarding_actions,
        sender=Onboarding,
        dispatch_uid="post_save_onboarding",
    )

    post_save.disconnect(
        execute_pre_offboarding_actions,
        sender=OrganizationChecklistRun,
        dispatch_uid="create_offboarding_run_document",
    )


def create_fake_organization():
    disconnect_org_post_savings()
    org, _ = Organization.objects.get_or_create(
        name=ALL_MY_COMPLIANCE_ORGS,
        website=ALL_MY_COMPLIANCE_ORG_FAKE_WEBSITE,
        defaults={
            'logo': '',
            'sfdc_id': ALL_MY_COMPLIANCE_ORG_FAKE_SFDC_ID,
            'description': 'Do not use this organization',
            'is_internal': True,
            'state': 'ACTIVE',
        },
    )

    org.feature_flags.filter(name=new_controls_feature_flag).delete()
    org.created_at = timezone.now()
    org.save()
    return org


class SeedAdmin(VersionAdmin):
    list_display = (
        'id',
        'organization',
        'custom_org_list',
        'created_by',
        'profile',
        'content_description',
        'created_at',
        'updated_at',
        'status',
    )
    fields = [
        'organization',
        'custom_org_list',
        'content_description',
        'seed_file',
        'profile',
        'status',
        'created_by',
        'status_detail',
    ]

    readonly_fields = ['created_at', 'updated_at', 'status_detail', 'created_by']
    autocomplete_fields = ['organization']

    def get_form(self, request, obj=None, **kwargs):
        form = super(SeedAdmin, self).get_form(request, obj=obj, **kwargs)
        form.base_fields['organization'].required = False
        return form

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        if db_field.name == 'organization':
            create_fake_organization()
            kwargs["queryset"] = Organization.objects.all().order_by('-created_at')

        return super(SeedAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )

    def save_model(self, request, obj, form, change):
        is_adding = not obj.pk
        obj.created_by = request.user
        super().save_model(request, obj, form, change)

        if is_adding:
            obj = obj.run()

            if obj.custom_org_list and obj.custom_org_list.file:
                pool.apply_async(
                    obj.create_and_run_upsert_seeds, args=(obj.custom_org_list.file,)
                )
            elif obj.organization.name == ALL_MY_COMPLIANCE_ORGS:
                pool.apply_async(obj.create_and_run_upsert_seeds, args=())


class SeedProfileAdmin(VersionAdmin):
    model = SeedProfile
    list_display = (
        'id',
        'name',
        'is_visible',
        'type',
        'content_description',
        'file',
        'created_at',
        'updated_at',
        'default_base',
    )


class FieldworkSeed(Seed):
    class Meta:
        proxy = True


class SeedFieldworkAdmin(VersionAdmin):
    list_display = ('id', 'created_at', 'updated_at', 'audit', 'status')
    fields = ['audit', 'seed_file', 'status', 'status_detail', 'created_by']

    def get_queryset(self, request):
        return self.model.objects.filter(audit__isnull=False)


@admin.register(MyComplianceMigration)
class MyComplianceMigrationAdmin(VersionAdmin):
    list_display = (
        'id',
        'organization',
        'frameworks_detail',
        'status_detail',
        'mapping_file',
        'status',
        'created_at',
        'updated_at',
    )


admin.site.register(Seed, SeedAdmin)
admin.site.register(SeedProfile, SeedProfileAdmin)
admin.site.register(FieldworkSeed, SeedFieldworkAdmin)
