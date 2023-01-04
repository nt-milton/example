import json
import logging
import os
import timeit
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import List, Union

import reversion
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import models
from django.db.models import F, JSONField, Max, Q
from django.db.models.expressions import RawSQL
from django.utils import timezone as dj_tz
from tinymce import models as tinymce_models

import integration.error_codes as error_codes
from integration.alerts import send_integration_failed_email
from laika.edas import eda_publisher
from laika.edas.edas import EdaMessage, EdaRegistry
from laika.storage import PublicMediaStorage
from laika.utils.dates import str_date_to_date_formatted
from laika.utils.exceptions import ServiceException, format_stack_in_one_line
from laika.utils.redis import get_redis_connection_from_pool
from objects.models import LaikaObject, LaikaObjectAlert, LaikaObjectType
from organization.models import Organization
from user.models import DISCOVERY_STATE_NEW, User
from vendor.models import OrganizationVendor, Vendor

from .constants import (
    ACTION_ITEM_FOR_PAYROLL_INTEGRATION,
    ALREADY_EXISTS,
    CONNECTION_STATUS,
    ERROR,
    ON_CREATE_PAYROLL_CONNECTION_ACCOUNT,
    PENDING,
    SUCCESS,
    SYNC,
)
from .exceptions import ConfigurationError, ConnectionAlreadyExists, TimeoutException
from .test_mode import is_connection_on_test_mode

TEST_MODE = 'test_mode'

BUSINESS_SUITES = 'business_suites'
CLOUD_SERVICE_PROVIDERS = 'cloud_service_providers'
DEVELOPER_TOOLS = 'developer_tools'
MONITORING_LOGGING = 'monitoring_logging'
PROJECT_MANAGEMENT = 'project_management'
IT_DEVICE_MANAGEMENT = 'it_device_management'
PAYROLL = 'payroll'
OTHER = 'other'
INTEGRATION_CATEGORIES = [
    (BUSINESS_SUITES, 'Business Suites'),
    (CLOUD_SERVICE_PROVIDERS, 'Cloud Service Providers'),
    (DEVELOPER_TOOLS, 'Developer Tools'),
    (MONITORING_LOGGING, 'Monitoring Logging'),
    (PROJECT_MANAGEMENT, 'Project Management'),
    (IT_DEVICE_MANAGEMENT, 'IT Device Management'),
    (PAYROLL, 'Payroll'),
    (OTHER, 'Other'),
]

CONNECTION_ACCOUNT_IDS = 'connection_account_ids'

logger = logging.getLogger(__name__)


def clean_up_connection_alias(alias: str) -> str:
    return alias.lower().replace(' ', '')


def validate_email_logo_extension(logo_file: File):
    ext = os.path.splitext(logo_file.name)[1]
    valid_extensions = ['.png']
    if ext and ext.lower() not in valid_extensions:
        raise ValidationError(f'Only {valid_extensions} extensions on email logo.')


def integration_email_logo_directory_path(instance, filename):
    return f'integrations/{instance.vendor.name}/{filename}'


def cache_keep_laika_object_ids(
    connection_account_id: int,
    laika_object_ids: List,
) -> None:
    if not laika_object_ids:
        return

    try:
        redis_connection = get_redis_connection_from_pool()
        stored_ids_count = redis_connection.sadd(
            f'connection_account_{connection_account_id}', *laika_object_ids
        )
        redis_connection.sadd(CONNECTION_ACCOUNT_IDS, connection_account_id)
        logger.info(
            f'Connection account {connection_account_id} - '
            f'Stored #{stored_ids_count} keep laika objects.'
        )
    except Exception as e:
        logger.info(
            f'Connection account {connection_account_id} - '
            f'Error storing #{len(laika_object_ids)} '
            f'keep laika objects on Redis. Error: {e}'
        )


class IntegrationManager(models.Manager):
    def actives(self, **kwargs):
        return self.filter(
            Q(metadata__disabled=False) | Q(metadata__disabled__isnull=True)
        )


class Integration(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    description = models.TextField()
    metadata = JSONField(blank=True, null=True)
    requirements = models.TextField(blank=True)
    category = models.CharField(
        max_length=36, choices=INTEGRATION_CATEGORIES, default=OTHER
    )
    email_logo = models.FileField(
        storage=PublicMediaStorage(),
        upload_to=integration_email_logo_directory_path,
        max_length=1024,
        blank=True,
        null=True,
        validators=[validate_email_logo_extension],
    )
    objects = IntegrationManager()

    def __str__(self):
        return f'{self.vendor.name} Integration'

    def laika_objects(self):
        laika_objects = self.metadata.get('laika_objects')
        return laika_objects.split(',') if laika_objects else []

    def get_requirements(self):
        return self.requirements.split('\n') if self.requirements != '' else None

    def get_alerts_with_regex(self, error):
        return (
            self.alerts.filter(error=error)
            .exclude(error_response_regex__isnull=True)
            .exclude(error_response_regex__exact='')
            .all()
        )

    def get_alert_without_regex(self, error):
        return self.alerts.filter(
            Q(error=error),
            Q(error_response_regex__isnull=True) | Q(error_response_regex__exact=''),
        ).first()

    def get_latest_version(self):
        latest_version = self.versions.aggregate(Max('version_number'))
        versions = self.versions.filter(
            version_number=latest_version.get('version_number__max')
        )
        if versions.exists():
            return versions.first()

        return None

    def save(self, *args, **kwargs):
        created = self.pk is None
        super(Integration, self).save(*args, **kwargs)
        if created:
            metadata = self.metadata
            if 'permissions' not in metadata:
                metadata['permissions'] = {}
            self.versions.create(
                version_number='1.0.0',
                description=f'Initial version for {self.vendor.name} integration',
                metadata=metadata,
            )

    class Meta:
        ordering = [F('metadata').desc(nulls_last=True)]


class IntegrationVersion(models.Model):
    version_number = models.CharField(max_length=15, blank=False, null=False)
    description = models.TextField(blank=True, null=True)
    metadata = JSONField(blank=True, null=True)
    integration = models.ForeignKey(
        Integration, on_delete=models.CASCADE, related_name='versions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f'{self.version_number} {self.integration.vendor.name} Integration Version'
        )


class ConnectionAccountManager(models.Manager):
    def clean_up_laika_objects(
        self,
        connection_account,
        laika_object_type: Union[LaikaObjectType, None] = None,
        keep_ids: Union[List, None] = None,
        soft_delete: bool = False,
    ):
        whole_function_time = timeit.default_timer()
        if not keep_ids:
            keep_ids = []

        cache_keep_laika_object_ids(
            connection_account_id=connection_account.id, laika_object_ids=keep_ids
        )
        delete_filter = {'connection_account_id': connection_account.id}
        if laika_object_type:
            delete_filter['object_type'] = laika_object_type
        objects_to_clean = clean_criteria(connection_account, delete_filter, keep_ids)
        if objects_to_clean is None:
            cleanup_time = timeit.default_timer() - whole_function_time
            logger.info(
                f'Connection account {connection_account.id}'
                f' - Keep IDs count {len(keep_ids)} nothing to delete'
                f' - Cleanup laika objects operation took {cleanup_time} seconds'
            )
            return None
        logger.info(
            f'Connection account {connection_account.id} - '
            f'Keep IDs count {len(keep_ids)}, '
            f'Soft delete {soft_delete}'
        )
        if soft_delete:
            objects_to_clean_qs = objects_to_clean.filter(deleted_at=None)
            objects_to_clean_ids = list(
                objects_to_clean_qs.values_list('id', flat=True)
            )
            logger.info(
                f'Connection account {connection_account.id} - '
                f'Soft deleting objects {objects_to_clean_ids}'
            )

            objects_to_clean_qs.update(
                deleted_at=datetime.now(timezone.utc).isoformat()
            )
        else:
            objects_to_clean._raw_delete(using=self.db)

        cleanup_time = timeit.default_timer() - whole_function_time
        logger.info(
            f'Connection account {connection_account.id} - Cleanup '
            f'laika objects operation took {cleanup_time} seconds'
        )

    def actives(self, **kwargs):
        return self.filter(status__in=[ERROR, SUCCESS], **kwargs)

    @staticmethod
    def validate_duplicated_alias(organization, integration, alias):
        all_connections = ConnectionAccount.objects.filter(
            organization=organization,
            integration=integration,
        )
        for connection in all_connections.all():
            current_connection_alias = clean_up_connection_alias(connection.alias)
            if current_connection_alias == clean_up_connection_alias(alias):
                raise ServiceException('Connection already exists')


class ErrorCatalogue(models.Model):
    class Meta:
        ordering = ['code']
        constraints = [
            models.UniqueConstraint(
                fields=['code'], name='integration_unique_error_code'
            )
        ]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    code = models.CharField(max_length=20, blank=False, null=False)
    error = models.CharField(max_length=100, blank=False, null=False)
    failure_reason_mail = models.CharField(
        max_length=100, blank=False, null=False, default=''
    )
    send_email = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    default_message = tinymce_models.HTMLField(blank=True, null=True, default='')
    default_wizard_message = tinymce_models.HTMLField(blank=True, null=True, default='')

    def __str__(self):
        return f'{self.code} - {self.error}'


class IntegrationAlert(models.Model):
    class Meta:
        ordering = ['integration__vendor']
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'integration',
                    'error',
                    'error_response_regex',
                    'wizard_error_code',
                ],
                name='integration_error_re_unique_error_message',
            )
        ]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    integration = models.ForeignKey(
        Integration, on_delete=models.CASCADE, related_name='alerts'
    )
    error = models.ForeignKey(
        ErrorCatalogue, on_delete=models.CASCADE, related_name='integrations'
    )
    error_message = tinymce_models.HTMLField(blank=True, null=True, default='')
    error_response_regex = models.CharField(
        max_length=500, blank=True, null=True, default=''
    )
    wizard_message = tinymce_models.HTMLField(blank=True, null=True, default='')
    wizard_error_code = models.CharField(
        max_length=50, blank=True, null=True, default=''
    )

    def __str__(self):
        return f'Integration {self.integration.id}, error {self.error}'


class ConnectionAccountDebugAction(models.Model):
    class Meta:
        ordering = ['-created_at']

    name = models.CharField(max_length=100)
    status = models.CharField(max_length=50)
    description = tinymce_models.HTMLField(blank=True, null=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.name}'


class ConnectionAccount(models.Model):
    class Meta:
        ordering = ['-created_at']

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    alias = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=CONNECTION_STATUS, default=PENDING)
    error_code = models.CharField(
        max_length=20,
        choices=error_codes.ERROR_CODES,
        default=error_codes.NONE,
    )
    send_mail_error = models.BooleanField(default=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='connection_accounts'
    )
    integration = models.ForeignKey(
        Integration, on_delete=models.CASCADE, related_name='connection_accounts'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        related_name='connected_integrations',
        blank=True,
        null=True,
    )
    debug_status = models.ForeignKey(
        ConnectionAccountDebugAction,
        on_delete=models.SET_NULL,
        related_name='connection_accounts',
        blank=True,
        null=True,
    )
    control = models.UUIDField(default=uuid.uuid4)
    authentication = JSONField()
    configuration_state = JSONField()
    result = JSONField(default=dict)
    objects = ConnectionAccountManager()
    integration_version = models.ForeignKey(
        IntegrationVersion,
        on_delete=models.SET_NULL,
        related_name='connection_accounts',
        blank=True,
        null=True,
    )

    def __str__(self):
        return f'{self.alias}'

    def _log_str_connection_error(self):
        return (
            f'Error with the connection id: {self.id}, '
            + f'name: {self.alias}. '
            + f'In Organization id: {self.organization.id}, '
            + f'name: {self.organization.name}. '
            + f'From Integration id: {self.integration.id}, '
            + f'vendor_name: {self.integration.vendor.name}. '
            + f'Error_code: {self.error_code}. '
        )

    @contextmanager
    def connection_attempt(self, success_status=SUCCESS):
        if is_connection_on_test_mode(self.id):
            logger.info(f'Connection account {self.id} running on test mode')
            yield
            return
        status = ERROR
        self.clean_connection_result()
        try:
            self.status = SYNC
            self.save()
            self.process_integration_log()
            yield
            if not self.id:
                logger.info('Connection account deleted.')
                return
            logger.info(f'Connection account {self.id} finished.')
            status = success_status
            self.error_code = error_codes.NONE
            self.configuration_state['last_successful_run'] = dj_tz.now().timestamp()
        except ConnectionAlreadyExists:
            status = ALREADY_EXISTS
            self.error_code = error_codes.NONE
            raise
        except TimeoutException as timeout_exc:
            self.error_code = error_codes.CONNECTION_TIMEOUT
            self.result.update(dict(error_response=str(timeout_exc)))
            self.log_error_exception(timeout_exc)
            raise
        except ConfigurationError as e:
            self.error_code = e.error_code
            self.result.update(dict(error_response=str(e.error_response)))
            self.log_connection_error(e)
            send_integration_failed_email(self, self.error_email_already_sent())
            raise
        except Exception as exc:
            self.error_code = error_codes.OTHER
            self.result.update(dict(error_response=str(exc)))
            self.log_error_exception(exc)
            send_integration_failed_email(self, self.error_email_already_sent())
            raise
        finally:
            with reversion.create_revision():
                self.status = status
                self.update_status_on_account_object()
                self.clear_debug_status_on_success()
                self.save()
                reversion.set_comment(
                    f'Connection account executed and ended on {self.status} status'
                )
                self.broadcast_payroll_on_success()
            self.process_integration_log(action='Ended')

    def log_connection_error(self, exception):
        logger.warning(
            self._log_str_connection_error()
            + f'Error_description: {exception.error_message}'
        )

    def log_error_exception(self, exception):
        logger.exception(
            self._log_str_connection_error()
            + f'Error: {format_stack_in_one_line(exception)}'
        )

    def process_integration_log(self, action: str = 'Started') -> None:
        logger.info(
            f'Connection account {self.id} - {action} '
            f'integration with vendor {self.integration.vendor} '
            f'ended on status {self.status}'
        )

    def update_status_on_account_object(self) -> None:
        account_object = self.laika_objects.filter(
            object_type__type_name='account', is_manually_created=False
        ).first()
        if account_object and self.status in [SUCCESS, ERROR]:
            is_active = self.status == SUCCESS
            account_object.data['Is Active'] = is_active
            account_object.save()

    def clear_debug_status_on_success(self):
        if self.status == SUCCESS:
            self.debug_status = None

    def broadcast_payroll_on_success(self):
        try:
            if self.status == SUCCESS and self.integration.category == PAYROLL:
                broadcast_payroll_connection_account_success(self)
        except Exception as e:
            logger.warning(f'An error occurred when broadcasting message. Error: {e}')

    @contextmanager
    def connection_error(
        self, error_code: str = None, keep_exception_error: bool = False
    ):
        self.clean_connection_result()
        try:
            self.status = PENDING
            self.save()
            yield
            self.error_code = error_codes.NONE
        except ConfigurationError as e:
            self.result.update(dict(error_response=str(e.error_response)))
            self.error_code = (
                e.error_code if keep_exception_error else error_codes.USER_INPUT_ERROR
            )
            self.log_connection_error(e)
            send_integration_failed_email(self, self.error_email_already_sent())
            if error_code:
                vendor = self.integration.vendor.name
                alert = IntegrationAlert.objects.filter(
                    integration__vendor__name=vendor, wizard_error_code=error_code
                ).first()
                if not alert:
                    catalogue_error = ErrorCatalogue.objects.get(
                        code=error_codes.USER_INPUT_ERROR
                    )
                    e.error_message = json.dumps(
                        dict(
                            wizardErrorMessage=catalogue_error.default_wizard_message,
                            integrationAlertCode=error_code,
                        )
                    )
                else:
                    e.error_message = (
                        json.dumps(
                            dict(
                                wizardErrorMessage=alert.wizard_message,
                                integrationAlertCode=error_code,
                            )
                        )
                        if alert
                        else ''
                    )
                e.is_user_input_error = True
                raise
            self.error_code = e.error_code
            self.status = PENDING
            raise
        finally:
            self.save()

    def delete(self, *args, **kwargs):
        self.remove_laika_object_alert()
        self.clean_up_laika_objects()
        super(ConnectionAccount, self).delete(*args, **kwargs)

    def clean_connection_result(self):
        self.result = {}

    def clean_up_laika_objects(
        self,
        *,
        laika_object_type: Union[LaikaObjectType, None] = None,
        keep_ids: Union[List, None] = None,
        soft_delete: bool = False,
    ):
        ConnectionAccount.objects.clean_up_laika_objects(
            connection_account=self,
            laika_object_type=laika_object_type,
            keep_ids=keep_ids,
            soft_delete=soft_delete,
        )

    def error_email_already_sent(self):
        filtered_connections = ConnectionAccount.objects.filter(
            created_by=self.created_by,
            organization=self.organization,
            integration=self.integration,
        )
        for connection in filtered_connections.all():
            sent_date = connection.result.get('email_sent', None)
            if (
                self.updated_at.date() == date.today()
                and self.error_code == connection.error_code
                and self.id == connection.id
                and self.error_code != error_codes.NONE
                and self.status != SUCCESS
                and sent_date is not None
            ):
                return True
            if not sent_date:
                continue
            if str_date_to_date_formatted(sent_date).date() == date.today():
                return True
        return False

    @property
    def settings(self):
        return self.configuration_state.get('settings', {})

    @property
    def credentials(self) -> dict:
        return self.configuration_state.get('credentials', {})

    @property
    def access_token(self):
        return self.authentication.get('access_token')

    def set_prefetched_options(self, field, options):
        if len(options) > 0:
            self.authentication[f'prefetch_{field}'] = options

    def get_error_in_catalogue(self):
        error_qs = ErrorCatalogue.objects.filter(code=self.error_code)
        if not error_qs.exists():
            return None
        return error_qs.first()

    @property
    def people_amount(self):
        return self.people.all().count()

    @property
    def discovered_people_amount(self):
        return self.people.filter(discovery_state=DISCOVERY_STATE_NEW).count()

    def remove_laika_object_alert(self):
        whole_function_time = timeit.default_timer()
        from alert.models import Alert

        laika_object_alerts = LaikaObjectAlert.objects.filter(
            laika_object__connection_account_id=self.id
        ).prefetch_related('alert')
        chunk_size = 2000
        num_records = 0
        while True:
            query_chunk = laika_object_alerts.iterator(chunk_size=chunk_size)
            alert_ids = []
            queryset = list(query_chunk)
            num_records += len(queryset)
            if len(queryset) == 0:
                operation_time = timeit.default_timer() - whole_function_time
                logger.info(
                    'Laika object alerts deleted for this connection account '
                    f'id - {self.id}, history operation took '
                    f'{operation_time} seconds for {num_records} records'
                )
                return
            for item in queryset:
                alert_ids.append(item.alert.id)
            else:
                alerts = Alert.objects.filter(id__in=alert_ids)
                laika_object_alerts._raw_delete(using=laika_object_alerts.db)
                alerts._raw_delete(using=alerts.db)

    def bulk_update_objects_connection_name(self, new_alias: str) -> int:
        formatted_alias = f'"{new_alias}"'
        updated_objects = self.laika_objects.update(
            data=RawSQL(
                """jsonb_set(data, '{"Connection Name"}', %s, false)""",
                [formatted_alias],
            )
        )
        logger.info(
            f'Connection account {self.id} - Count of objects modified with '
            f'new connection name {new_alias} are {updated_objects}'
        )
        return updated_objects

    def clean(self):
        if (self.organization_id and self.created_by_id) and (
            self.created_by.organization != self.organization
        ):
            raise ValidationError(
                {
                    'created_by': (
                        'The chosen user must belong to the selected organization'
                        f' ({self.organization})'
                    )
                }
            )


class OrganizationVendorUserSSO(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['email', 'vendor', 'connection_account'],
                name='email_vendor_connection_account',
            )
        ]

    status = models.CharField(max_length=100, blank=True)
    connection_account = models.ForeignKey(
        ConnectionAccount, on_delete=models.CASCADE, related_name='vendor_users_sso'
    )
    name = models.CharField(max_length=100)
    email = models.CharField(max_length=100)
    vendor = models.ForeignKey(
        OrganizationVendor, on_delete=models.CASCADE, related_name='sso_users'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sso_user', null=True
    )


def clean_criteria(connection_account, delete_filter, keep_ids):
    if (
        connection_account.integration.metadata.get('delete', 'v1') == 'v1'
        or not keep_ids
    ):
        return LaikaObject.objects.filter(**delete_filter).exclude(id__in=keep_ids)

    all_lo_ids = set(
        LaikaObject.objects.filter(**delete_filter).values_list('id', flat=True)
    )
    to_delete = all_lo_ids - set(keep_ids)
    if not to_delete:
        return None
    if len(to_delete) < len(keep_ids):
        return LaikaObject.objects.filter(id__in=to_delete, **delete_filter)
    else:
        return LaikaObject.objects.filter(**delete_filter).exclude(id__in=keep_ids)


def broadcast_payroll_connection_account_success(
    connection_account: ConnectionAccount,
) -> bool:
    return eda_publisher.submit_event(
        message=EdaMessage.build(
            event=EdaRegistry.event_lookup(ON_CREATE_PAYROLL_CONNECTION_ACCOUNT),
            organization_id=str(connection_account.organization.id),
            action_item_ref_id=ACTION_ITEM_FOR_PAYROLL_INTEGRATION,
            connection_account_id=connection_account.id,
        )
    )
