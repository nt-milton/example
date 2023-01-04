import logging

from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.db.models.query import QuerySet
from django.http.request import HttpRequest
from reversion.admin import VersionAdmin

from alert.models import Alert
from audit.models import AuditorAuditFirm
from feature.constants import okta_feature_flag
from laika.aws import cognito
from laika.aws.cognito import delete_cognito_users
from laika.okta.api import OktaApi
from laika.settings import ENVIRONMENT
from laika.utils.InputFilter import InputFilter

from .concierge_helpers import (
    create_cognito_concierge_user,
    send_concierge_user_email_invitation,
)
from .helpers import manage_cognito_user, manage_okta_user
from .models import (
    Auditor,
    Concierge,
    Officer,
    Partner,
    Team,
    TeamMember,
    UserProxy,
    WatcherList,
)
from .permissions import add_concierge_user_to_group

User = get_user_model()

OktaApi = OktaApi()

logger = logging.getLogger(__name__)

INVITATION_SENT_SUCCESSFULLY = 'Invitation sent successfully'
user_readonly = ['policies_reviewed', 'updated_at']

auth_fields = [
    'password',
    'last_login',
    'invitation_sent',
    'password_expired',
    'mfa',
]

if ENVIRONMENT in ['local', 'dev']:
    auth_fields.append('groups')
    auth_fields.append('user_permissions')
else:
    auth_fields.append('groups')
    user_readonly.append('groups')


class AlertsInlineAdmin(admin.TabularInline):
    model = Alert
    fields = ['sender', 'type', 'comment_id']
    readonly_fields = ['sender', 'type', 'comment_id']
    fk_name = 'receiver'

    def sender(self, instance):
        return instance.sender_name

    def type(self, instance):
        return instance.type

    def comment_id(self, instance):
        return instance.comment_alert.comment.id

    classes = ['collapse']


class AddUserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput())

    class Meta:
        model = User
        fields = '__all__'

    def clean_password(self):
        return make_password(self.cleaned_data['password'])


class IdFilter(InputFilter):
    parameter_name = 'id'
    title = 'User ID'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(id=self.value().strip())


class UsernameFilter(InputFilter):
    parameter_name = 'username'
    title = 'Username'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(username=self.value().strip())


class FirstnameFilter(InputFilter):
    parameter_name = 'first_name'
    title = 'Name'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(first_name__icontains=self.value().strip())


class LastnameFilter(InputFilter):
    parameter_name = 'last_name'
    title = 'Lastname'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(last_name__icontains=self.value().strip())


class EmailFilter(InputFilter):
    parameter_name = 'email'
    title = 'Email'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(email__icontains=self.value().strip())


class OrganizationFilter(InputFilter):
    parameter_name = 'organization'
    title = 'Organization Name'

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(organization__name__icontains=self.value().strip())


class LaikaUserAdmin(VersionAdmin):
    ordering = ('-updated_at', 'organization__name')

    fieldsets = (
        (
            'Auth',
            {
                'fields': auth_fields,
            },
        ),
        (
            'General',
            {
                'fields': [
                    'first_name',
                    'last_name',
                    'email',
                    'is_active',
                    'date_joined',
                    'deleted_at',
                    'updated_at',
                ],
            },
        ),
        (
            'Assign',
            {
                'fields': [
                    'username',
                    'organization',
                    'role',
                    'is_superuser',
                    'is_staff',
                    'user_preferences',
                    'compliant_completed',
                    'security_training',
                    'assigned_trainings_completed',
                    'policies_reviewed',
                ]
            },
        ),
        (
            'People Data',
            {
                'fields': [
                    'profile_picture',
                    'title',
                    'manager',
                    'department',
                    'phone_number',
                    'employment_type',
                    'employment_status',
                    'employment_subtype',
                    'background_check_status',
                    'background_check_passed_on',
                    'start_date',
                    'end_date',
                ]
            },
        ),
        (
            'Integration & Vendor',
            {
                'fields': [
                    'connection_account',
                    'discovery_state',
                    'finch_uuid',
                ]
            },
        ),
    )

    list_display = (
        'id',
        'first_name',
        'last_name',
        'username',
        'email',
        'organization',
        'role',
        'last_login',
        'updated_at',
    )
    list_filter = (
        'role',
        IdFilter,
        UsernameFilter,
        OrganizationFilter,
        FirstnameFilter,
        LastnameFilter,
        EmailFilter,
        'password_expired',
        'discovery_state',
        'is_staff',
    )
    search_fields = ('first_name',)
    autocomplete_fields = ['organization', 'manager']
    form = AddUserForm
    inlines = [AlertsInlineAdmin]
    actions = [
        'reset_mfa',
        'send_email_invitation',
    ]
    readonly_fields = user_readonly
    change_list_template = "admin/user_change_list.html"

    def reset_mfa(self, request, queryset):
        for user in queryset.filter(mfa=True):
            cognito.change_mfa_preference(user.username, False)
            user.mfa = False
            user.save()

    def send_email_invitation(self, request, queryset):
        for user in queryset:
            is_okta_active = user.organization.is_flag_active(okta_feature_flag)

            if is_okta_active:
                user, _ = manage_okta_user(user)
            else:
                user, _ = manage_cognito_user(user)

            if user:
                messages.info(request, 'Invitation sent successfully')
            else:
                messages.error(request, 'An error happened')

    def get_exclude(self, request, obj=None):
        if ENVIRONMENT == 'local' or ENVIRONMENT == 'dev':
            return None
        else:
            return ['user_permissions', 'groups']

    reset_mfa.short_description = 'Reset MFA settings'  # type: ignore
    send_email_invitation.short_description = 'Send Invitation'  # type: ignore

    def reversion_register(self, model, **options):
        options['exclude'] = (
            'last_login',
            'updated_at',
        )
        super().reversion_register(model, **options)


class OfficerAdmin(VersionAdmin):
    model = Officer
    list_display = ('name', 'organization', 'created_at', 'updated_at', 'user')
    list_filter = ('organization', 'name')


class TeamMemberInlineAdmin(admin.StackedInline):
    model = TeamMember


class TeamAdmin(VersionAdmin):
    model = Team
    list_display = ('name', 'organization', 'created_at', 'updated_at')
    list_filter = ('organization', 'name')
    inlines = [
        TeamMemberInlineAdmin,
    ]


class AuditFirmInlineAdmin(admin.TabularInline):
    model = AuditorAuditFirm

    fields = ['audit_firm']
    max_num = 1
    min_num = 1

    def audit_firm(self, instance):
        return instance.audit_firm.name


class AuditorAdmin(admin.ModelAdmin):
    model = Auditor
    inlines = [AuditFirmInlineAdmin]

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        if db_field.name == "user":
            kwargs["queryset"] = User.objects.filter(
                role__in=['AuditorAdmin', 'Auditor']
            )

        return super(AuditorAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )


class ConciergeAdmin(admin.ModelAdmin):
    model = Concierge
    search_fields = ('user__first_name',)

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        if db_field.name == "user":
            kwargs["queryset"] = User.objects.filter(role__in=['Concierge']).exclude(
                id__in=Concierge.objects.all().values('user_id')
            )

        return super(ConciergeAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )

    def save_model(self, request, obj, form, change):
        try:
            cognito_user = cognito.get_user(obj.user.username)
            if cognito_user:
                message = 'User already exists in Cognito Pool. Deleting existing user.'
                messages.warning(request, message)
                delete_cognito_users([obj.user.email])

            user_data = {
                'first_name': obj.user.first_name,
                'last_name': obj.user.last_name,
                'email': obj.user.email,
                'permission': obj.user.role,
            }

            cognito_user = create_cognito_concierge_user(user_data)
            obj.user.username = cognito_user.get('username')
            obj.user.save()

            add_concierge_user_to_group(obj.user)
            send_concierge_user_email_invitation(obj.user, cognito_user)
            messages.info(request, INVITATION_SENT_SUCCESSFULLY)
        except Exception as e:
            logger.exception(
                'There was a problem setting up concierge with'
                f'id {obj.user.id} credentials and invite. Error: {e}'
            )
            delete_cognito_users([obj.user.email])

        super().save_model(request, obj, form, change)


class WatcherListAdmin(admin.ModelAdmin):
    list_display = ('id', 'organization', 'monitor')
    list_filter = ('organization_monitor__organization',)
    search_fields = [
        'id',
        'organization_monitor__organization__name',
        'organization_monitor__monitor__name',
    ]
    filter_horizontal = ['users']

    def organization(self, instance):
        return instance.organization.name

    def monitor(self, instance):
        return instance.organization_monitor.monitor


class AllLaikaUserAdmin(VersionAdmin):
    ordering = ('-deleted_at', 'organization__name')

    fieldsets = (
        (
            'General',
            {
                'fields': [
                    'first_name',
                    'last_name',
                    'email',
                    'is_active',
                    'date_joined',
                    'deleted_at',
                    'updated_at',
                ],
            },
        ),
        (
            'Auth',
            {
                'fields': auth_fields,
            },
        ),
        (
            'Assign',
            {
                'fields': [
                    'username',
                    'organization',
                    'role',
                    'is_superuser',
                    'is_staff',
                    'user_preferences',
                    'compliant_completed',
                    'security_training',
                    'assigned_trainings_completed',
                    'policies_reviewed',
                ]
            },
        ),
        (
            'People Data',
            {
                'fields': [
                    'profile_picture',
                    'title',
                    'manager',
                    'department',
                    'phone_number',
                    'employment_type',
                    'employment_status',
                    'employment_subtype',
                    'background_check_status',
                    'background_check_passed_on',
                    'start_date',
                    'end_date',
                ]
            },
        ),
        (
            'Integration & Vendor',
            {
                'fields': [
                    'connection_account',
                    'discovery_state',
                    'finch_uuid',
                ]
            },
        ),
    )

    list_display = (
        'id',
        'first_name',
        'last_name',
        'username',
        'email',
        'organization',
        'role',
        'last_login',
        'deleted_at',
    )
    list_filter = (
        IdFilter,
        UsernameFilter,
        OrganizationFilter,
        FirstnameFilter,
        LastnameFilter,
        EmailFilter,
    )

    search_fields = (
        'first_name',
        'last_name',
    )

    readonly_fields = user_readonly

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        qs = self.model.all_objects.exclude(deleted_at=None)
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet) -> None:
        for obj in queryset:
            obj.hard_delete()

    def delete_model(self, request: HttpRequest, obj) -> None:
        return obj.hard_delete()


class PartnerAdmin(admin.ModelAdmin):
    list_display = ('name', 'type')
    list_filter = ('type',)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'users':
            kwargs['queryset'] = User.objects.filter(role='Partner')
        return super(PartnerAdmin, self).formfield_for_manytomany(
            db_field, request, **kwargs
        )


admin.site.register(User, LaikaUserAdmin)
admin.site.register(Officer, OfficerAdmin)
admin.site.register(Team, TeamAdmin)
admin.site.unregister(Group)
admin.site.register(Auditor, AuditorAdmin)
admin.site.register(Concierge, ConciergeAdmin)
admin.site.register(WatcherList, WatcherListAdmin)
admin.site.register(Partner, PartnerAdmin)
admin.site.register(UserProxy, AllLaikaUserAdmin)

if ENVIRONMENT in ['local', 'dev']:
    admin.site.register(Group, GroupAdmin)
