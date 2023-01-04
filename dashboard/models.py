import logging
import uuid

from django.conf import settings
from django.db import models
from django.db.models import F

from action_item.constants import (
    TYPE_ACCESS_REVIEW,
    TYPE_CONTROL,
    TYPE_POLICY,
    TYPE_QUICK_START,
)
from monitor.models import OrganizationMonitor
from organization.models import Organization
from program.models import SubTask
from user.models import User

logger = logging.getLogger('dashboard')


class TaskTypes(models.TextChoices):
    MONITOR_TASK = 'monitor_task', 'Monitor'


class TaskSubTypes(models.TextChoices):
    MONITOR = 'monitor', 'Monitor'


class UserTaskStatus(models.TextChoices):
    NOT_STARTED = 'not_started', 'Not Started'
    PENDING = 'pending', 'Pending'
    COMPLETED = 'completed', 'Completed'


class ActionItemsTypes(models.TextChoices):
    CONTROL = 'control', 'Control'


USER_TASK_TYPES = [TaskTypes.MONITOR_TASK]

CONTROL_ACTION_ITEM_TASK_TYPE = [ActionItemsTypes.CONTROL]

NON_SUBTYPE_TASK_TYPES = []
NON_SUBTYPE_TASK_TYPES.extend(USER_TASK_TYPES)
NON_SUBTYPE_TASK_TYPES.extend(CONTROL_ACTION_ITEM_TASK_TYPE)


class DefaultTask(models.TextChoices):
    """
    Default tasks name
    It should have uniques name since it will be used in task name field in
    task form.
    """

    LIBRARY_TRAINING_VIDEO = 'library_training_video', 'Library Video Training'
    DATAROOM_TRAINING_VIDEO = 'dataroom_training_video', 'Dataroom Video Training'
    COMPLETE_TRAININGS = 'complete_trainings', 'Complete Trainings'
    MONITOR_TASK = 'monitor_task', 'Monitor Task'


class ActionItemBaseModel(models.Model):
    model_id = models.UUIDField(blank=True, null=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='action_items'
    )
    unique_action_item_id = models.CharField(max_length=264)
    created_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(blank=True, null=True)
    assignee = models.ForeignKey(
        User,
        related_name='action_item_assignee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    start_date = models.DateField(blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    completed_on = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=50)
    type = models.CharField(max_length=50)
    group = models.CharField(max_length=50)
    description = models.TextField()
    reference_url = models.TextField()
    sort_index = models.IntegerField()
    # reference_id & reference_name columns added to display
    # control reference_id and control name for control action items
    reference_id = models.CharField(max_length=50, blank=True, null=True)
    reference_name = models.TextField(blank=True, null=True)
    # is_required & is_recurrent columns added to by able to filter
    # by required or recurrent action items
    is_required = models.BooleanField(blank=True, default=False)
    is_recurrent = models.BooleanField(blank=True, default=False)

    class Meta:
        abstract = True


class ActionItem(ActionItemBaseModel):
    class Meta:
        managed = getattr(settings, 'UNDER_TEST', False)
        db_table = 'dashboard_view'

        permissions = [('view_dashboard', 'Can view dashboard')]

        ordering = [F('due_date').asc(nulls_last=True)]

    @property
    def seen_action_item(self):
        return action_item_seen(self)

    @property
    def subtask_text(self):
        """
        This property is only valid for playbooks task. Otherwise it returns
        an empty string
        """

        if self.type in USER_TASK_TYPES + [
            TYPE_QUICK_START,
            TYPE_CONTROL,
            TYPE_POLICY,
            TYPE_ACCESS_REVIEW,
        ]:
            return ''
        try:
            return SubTask.objects.get(id=self.unique_action_item_id).text
        except SubTask.DoesNotExist:
            logger.warning(
                f'Subtask item with id {self.unique_action_item_id} was not found'
            )
            return ''


class TaskView(ActionItemBaseModel):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='task_view_action_items',
    )
    assignee = models.ForeignKey(
        User,
        related_name='task_view_action_item_assignee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        managed = getattr(settings, 'UNDER_TEST', False)
        db_table = 'task_view'
        permissions = [('view_dashboard', 'Can view dashboard')]
        ordering = [F('due_date').asc(nulls_last=True)]

    @property
    def seen_action_item(self):
        return action_item_seen(self)


class ActionItemMetadata(models.Model):
    seen = models.BooleanField(default=False)
    action_item_id = models.CharField(max_length=264, unique=False)
    assignee = models.ForeignKey(
        User,
        related_name='action_item_metadata_assignee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name_plural = 'action_item_metadata'
        unique_together = (('action_item_id', 'assignee'),)


class Task(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=200, unique=True)
    description = models.CharField(max_length=250)
    task_type = models.CharField(max_length=50, choices=TaskTypes.choices)
    task_subtype = models.CharField(max_length=25, choices=TaskSubTypes.choices)
    metadata = models.JSONField(default=dict, blank=True, null=True)

    def __str__(self):
        return self.name


class UserTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    completed_on = models.DateField(blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    seen = models.BooleanField(default=False)
    description = models.CharField(max_length=250, blank=True)
    reference_url = models.CharField(max_length=250, blank=True, default='')
    status = models.CharField(
        max_length=50,
        choices=UserTaskStatus.choices,
        default=UserTaskStatus.NOT_STARTED,
    )
    organization_monitor = models.ForeignKey(
        OrganizationMonitor, on_delete=models.CASCADE, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['assignee', 'task'], name='unique_user_task'
            ),
        ]

    def __str__(self):
        return f'{self.assignee} - {self.task}'


def action_item_seen(action_item):
    if action_item in USER_TASK_TYPES:
        return UserTask.objects.get(id=action_item.model_id).seen
    if not ActionItemMetadata.objects.filter(
        action_item_id=action_item.unique_action_item_id, assignee=action_item.assignee
    ).exists():
        logger.warning(
            f'Action item with id {action_item.unique_action_item_id} assigned '
            f'to {action_item.assignee.id} does not exist in action item '
            'metadata'
        )
        return False
    else:
        action_item_metadata = ActionItemMetadata.objects.get(
            action_item_id=action_item.unique_action_item_id,
            assignee=action_item.assignee,
        )
        return action_item_metadata.seen
