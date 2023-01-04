from django.db import DatabaseError, models
from django.utils.translation import gettext_lazy as _
from tinymce import models as tinymce_models

from certification.models import Certification
from control.models import Control
from monitor.launchpad import launchpad_mapper
from monitor.sqlutils import is_cloud_table
from organization.models import Organization
from search.search import launchpad_model, searchable_model
from tag.models import Tag
from user.models import User, WatcherList


class MonitorStatus(models.TextChoices):
    ACTIVE = 'active'
    INACTIVE = 'inactive'


class MonitorHealthCondition(models.TextChoices):
    RETURN_RESULTS = 'return_results', _('Return results')
    EMPTY_RESULTS = 'empty_results', _('Empty results')


class MonitorInstanceStatus(models.TextChoices):
    HEALTHY = 'healthy'
    TRIGGERED = 'triggered'
    CONNECTION_ERROR = 'connection_error'
    NO_DATA_DETECTED = 'no_data_detected'


class MonitorRunnerType(models.TextChoices):
    LAIKA_CONTEXT = 'laika_context'
    ON_DEMAND = 'on_demand'


class MonitorFrequency(models.TextChoices):
    DAILY = 'daily'


class MonitorType(models.TextChoices):
    SYSTEM = 'system_monitor'
    CUSTOM = 'custom_monitor'


class MonitorUrgency(models.TextChoices):
    URGENT = 'urgent'
    STANDARD = 'standard'
    LOW = 'low'


class MonitorSubscriptionEventType(models.TextChoices):
    SUBSCRIBED = 'subscribed'
    UNSUBSCRIBED = 'unsubscribed'


class MonitorExclusionEventType(models.TextChoices):
    CREATED = 'created'
    DELETED = 'deleted'
    RENEWED = 'renewed'
    DEPRECATED = 'deprecated'
    UPDATED_JUSTIFICATION = 'updated_justification'


class MonitorUserEventsOptions(models.TextChoices):
    VIEW_DETAIL = 'view_detail'
    VIEW_DASHBOARD = 'view_dashboard'
    CLOSE_DYNAMIC_BANNER = 'close_dynamic_banner'


def infer_context_from_query(query: str) -> str:
    from monitor.sqlutils import get_selected_tables

    selected_tables = get_selected_tables(query)
    table_name = selected_tables[0][1] if len(selected_tables) > 0 else None
    is_context_on_demand = table_name and is_cloud_table(table_name)
    return (
        MonitorRunnerType.ON_DEMAND
        if is_context_on_demand
        else MonitorRunnerType.LAIKA_CONTEXT
    )


@searchable_model(type='monitor')
class Monitor(models.Model):
    name = models.CharField(max_length=128)
    query = models.TextField()
    source_systems = models.JSONField(null=True)
    control_references = models.TextField(
        null=True, blank=True, verbose_name='Control references'
    )
    control_reference_ids = models.TextField(
        blank=True, default='', verbose_name='Control references by id'
    )
    evidence_requests_references = models.TextField(
        null=True, blank=True, verbose_name='Evidence references'
    )
    evidence_requests_reference_ids = models.TextField(
        blank=True, default='', verbose_name='Evidence references by id'
    )
    tag_references = models.TextField(
        null=True, blank=True, verbose_name='Tag references'
    )
    subtask_reference = models.TextField(
        null=True, blank=True, verbose_name='Subtask reference'
    )
    validation_query = models.TextField(
        null=True, blank=True, verbose_name='Datasource Validation Query'
    )
    description = models.TextField()
    display_id = models.TextField(default='', blank=False)
    monitor_type = models.CharField(
        max_length=32, choices=MonitorType.choices, default=MonitorType.SYSTEM
    )
    urgency = models.CharField(
        max_length=32, choices=MonitorUrgency.choices, default='low'
    )
    status = models.CharField(max_length=32, choices=MonitorStatus.choices)
    health_condition = models.CharField(
        max_length=32, choices=MonitorHealthCondition.choices
    )
    frequency = models.CharField(max_length=32, choices=MonitorFrequency.choices)
    runner_type = models.CharField(max_length=32, choices=MonitorRunnerType.choices)
    parent_monitor = models.ForeignKey(
        'self', related_name='parent', null=True, on_delete=models.SET_NULL, blank=True
    )
    organization = models.ForeignKey(
        Organization,
        related_name='custom_monitors',
        null=True,
        on_delete=models.CASCADE,
        blank=True,
    )
    take_action = tinymce_models.HTMLField(blank=True, null=True, default='')
    fix_me_link = models.TextField(blank=True, null=True, default='')
    exclude_field = models.TextField(blank=True, null=True, default='')
    frameworks = models.ManyToManyField(Certification, related_name='monitors')

    def is_custom(self):
        return self.monitor_type == MonitorType.CUSTOM

    def save(self, *args, **kwargs):
        if self.id is not None:
            exclusions = MonitorExclusion.objects.filter(
                organization_monitor__monitor=self,
            ).exclude(key=self.exclude_field)
            exclusions.filter(is_active=True).update(is_active=False)
            MonitorExclusionEvent.objects.bulk_create(
                [
                    MonitorExclusionEvent(
                        monitor_exclusion=exclusion,
                        justification=exclusion.justification,
                        event_type=MonitorExclusionEventType.DELETED,
                    )
                    for exclusion in exclusions
                ]
            )
        if self.query and not self.is_custom():
            self.runner_type = infer_context_from_query(self.query)
        super(Monitor, self).save(*args, **kwargs)

    def __str__(self):
        return f'({self.monitor_type}) {self.name}'

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_custom_type",
                check=(
                    models.Q(
                        monitor_type=MonitorType.CUSTOM, organization__isnull=False
                    )
                    | models.Q(
                        monitor_type=MonitorType.SYSTEM,
                        parent_monitor__isnull=True,
                        organization__isnull=True,
                    )
                ),
            )
        ]


class MonitorSubscriptionEvent(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='monitor_subscription_event'
    )
    event_type = models.TextField(choices=MonitorSubscriptionEventType.choices)


@launchpad_model(context='monitor', mapper=launchpad_mapper)
class OrganizationMonitor(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['organization', 'monitor'], name='organization_monitor'
            ),
        ]

    name = models.CharField(max_length=128, default='', blank=True)
    query = models.TextField(default='', blank=True)
    description = models.TextField(default='', blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    monitor = models.ForeignKey(
        Monitor, related_name='organization_monitors', on_delete=models.CASCADE
    )
    watcher_list = models.OneToOneField(
        WatcherList,
        related_name='organization_monitor',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    controls = models.ManyToManyField(
        Control, related_name='organization_monitors', blank=True
    )
    tags = models.ManyToManyField(Tag, related_name='organization_monitors', blank=True)
    active = models.BooleanField()
    toggled_by_system = models.BooleanField(default=True)
    status = models.CharField(max_length=32, choices=MonitorInstanceStatus.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    urgency = models.CharField(
        max_length=32, choices=MonitorUrgency.choices, blank=True
    )

    @property
    def monitor_urgency(self):
        return self.urgency or self.monitor.urgency

    def save(self, *args, **kwargs):
        monitor = self.monitor
        if (
            monitor.organization
            and monitor.is_custom()
            and monitor.organization != self.organization
        ):
            raise DatabaseError('Custom monitor does not match organization')
        exclusions = MonitorExclusion.objects.filter(
            is_active=True,
            organization_monitor=self,
        ).exclude(organization_monitor__monitor=monitor)
        exclusions.update(is_active=False)
        MonitorExclusionEvent.objects.bulk_create(
            [
                MonitorExclusionEvent(
                    monitor_exclusion=exclusion,
                    justification=exclusion.justification,
                    event_type=MonitorExclusionEventType.DELETED,
                )
                for exclusion in exclusions
            ]
        )
        super(OrganizationMonitor, self).save(*args, **kwargs)

    def __str__(self):
        return f'({self.organization.name}) {self.monitor.name}'

    def is_flagged(self):
        return self.status == MonitorInstanceStatus.TRIGGERED


class MonitorResult(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    organization_monitor = models.ForeignKey(
        OrganizationMonitor, on_delete=models.CASCADE
    )
    result = models.JSONField()
    query = models.TextField(default='')
    status = models.CharField(max_length=32, choices=MonitorInstanceStatus.choices)
    health_condition = models.CharField(
        max_length=32, choices=MonitorHealthCondition.choices, default=''
    )
    execution_time = models.DecimalField(
        max_digits=7, decimal_places=3, default=0, blank=True
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f'{self.organization_monitor.monitor.name}'

    def can_exclude(self):
        if self.organization_monitor.monitor.is_custom():
            return False
        exclude_field = self.organization_monitor.monitor.exclude_field
        exclude_setup = self.is_exception_result() and exclude_field
        if not exclude_setup:
            return False
        if not self.result.get('data'):
            return True
        variables = self.result.get('variables') or []
        if not variables:
            return False
        first_vars = variables[0]
        return exclude_field in first_vars

    def is_exception_result(self):
        return self.health_condition == MonitorHealthCondition.EMPTY_RESULTS


class MonitorExclusion(models.Model):
    organization_monitor = models.ForeignKey(
        OrganizationMonitor, on_delete=models.CASCADE
    )
    exclusion_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    key = models.TextField()
    value = models.TextField()
    snapshot = models.JSONField()
    justification = models.TextField()

    @property
    def last_event(self):
        return (
            MonitorExclusionEvent.objects.filter(monitor_exclusion=self)
            .order_by('-event_date')
            .first()
        )


class MonitorExclusionEvent(models.Model):
    monitor_exclusion = models.ForeignKey(MonitorExclusion, on_delete=models.CASCADE)
    event_date = models.DateTimeField(auto_now=True)
    event_type = models.TextField(choices=MonitorExclusionEventType.choices)
    justification = models.TextField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, default=None, null=True)


class MonitorUserEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    event = models.TextField(choices=MonitorUserEventsOptions.choices)
    event_time = models.DateTimeField(auto_now_add=True)
    organization_monitor = models.ForeignKey(
        OrganizationMonitor, null=True, on_delete=models.SET_NULL
    )
