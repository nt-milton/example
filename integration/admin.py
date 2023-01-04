import logging
from multiprocessing.pool import ThreadPool

from django.contrib import admin
from django.http import HttpResponseRedirect
from reversion.admin import VersionAdmin

from user.models import User

from .forms import ConnectionAccountAdminForm, IntegrationAdminForm
from .models import (
    ConnectionAccount,
    ConnectionAccountDebugAction,
    ErrorCatalogue,
    Integration,
    IntegrationAlert,
    IntegrationVersion,
)
from .tasks import run_integration_on_test_mode
from .test_mode import test_state

pool = ThreadPool()


logger = logging.getLogger(__name__)


class ErrorCatalogueAdmin(VersionAdmin):
    list_display = (
        'code',
        'error',
        'failure_reason_mail',
        'send_email',
        'created_at',
        'updated_at',
    )
    search_fields = ('code', 'error')


class ConnectionAccountDebugActionAdmin(VersionAdmin):
    list_display = (
        'name',
        'status',
        'description',
        'created_at',
        'updated_at',
    )
    list_filter = ('name',)
    ordering = ['name']


class ConnectionAccountAdmin(VersionAdmin):
    form = ConnectionAccountAdminForm
    list_display = (
        'alias',
        'status',
        'error_code',
        'get_user_name',
        'get_organization_name',
        'get_integration_name',
        'created_at',
        'updated_at',
    )
    list_filter = (
        'organization',
        'integration',
        'error_code',
        'status',
        'debug_status',
    )
    search_fields = ('organization__name', 'alias', 'integration__vendor__name')

    change_form_template = (
        "admin/connection_account/connection_account_change_form.html"
    )

    def changelist_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['has_execute_all_error_connections_permission'] = (
            request.user.is_active and request.user.is_superuser
        )
        return super(ConnectionAccountAdmin, self).changelist_view(
            request, extra_context
        )

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['has_test_connection_account_permission'] = (
            request.user.is_active and request.user.is_superuser
        )
        return super(ConnectionAccountAdmin, self).change_view(
            request, object_id, form_url, extra_context
        )

    def get_urls(self):
        return super().get_urls()

    def response_change(self, request, obj):
        if '_execute_on_test_mode' in request.POST:
            connection_account_id = obj.id
            test_state.reset_test_mode(connection_account_id)
            run_integration_on_test_mode.delay(connection_id=connection_account_id)

            return HttpResponseRedirect(".")
        return super().response_change(request, obj)

    def get_organization_name(self, instance):
        return instance.organization.name

    def get_user_name(self, instance):
        return instance.created_by

    get_user_name.admin_order_field = 'created_by'  # type: ignore
    get_user_name.short_description = 'Created By'  # type: ignore

    get_organization_name.admin_order_field = 'organization'  # type: ignore
    get_organization_name.short_description = 'Organization Name'  # type: ignore

    def get_integration_name(self, instance):
        return instance.integration.vendor.name

    get_organization_name.short_description = 'Organization'  # type: ignore
    get_integration_name.short_description = 'Integration'  # type: ignore

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'created_by':
            connection_account_id = request.resolver_match.kwargs.get('object_id')
            if connection_account_id:
                connection_account = ConnectionAccount.objects.get(
                    id=connection_account_id
                )
                kwargs["queryset"] = User.objects.filter(
                    organization=connection_account.organization, is_active=True
                )

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class IntegrationErrorsInlineAdmin(admin.TabularInline):
    model = IntegrationAlert
    fields = (
        'error',
        'wizard_error_code',
        'error_response_regex',
        'error_message',
        'wizard_message',
    )


class IntegrationAdmin(VersionAdmin):
    form = IntegrationAdminForm
    list_display = ('get_vendor_name', 'category', 'description')
    list_filter = ('category',)
    inlines = [
        IntegrationErrorsInlineAdmin,
    ]
    ordering = ['vendor__name']

    def get_vendor_name(self, instance):
        return instance.vendor.name

    get_vendor_name.admin_order_field = 'vendor'  # type: ignore
    get_vendor_name.short_description = 'Vendor Name'  # type: ignore


class IntegrationVersionAdmin(VersionAdmin):
    list_display = ('integration', 'version_number', 'description')
    list_filter = ('integration__vendor__name',)
    ordering = ['version_number']


admin.site.register(ConnectionAccount, ConnectionAccountAdmin)
admin.site.register(ConnectionAccountDebugAction, ConnectionAccountDebugActionAdmin)
admin.site.register(Integration, IntegrationAdmin)
admin.site.register(ErrorCatalogue, ErrorCatalogueAdmin)
admin.site.register(IntegrationVersion, IntegrationVersionAdmin)
