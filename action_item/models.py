import re

from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from django.utils.timezone import now

from action_item.launchpad import launchpad_mapper
from alert.models import Alert
from program.utils.alerts import create_alert
from search.search import launchpad_model
from tag.models import Tag
from user.models import User


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


class ActionItemStatus(models.TextChoices):
    NEW = 'new', 'New'
    PENDING = 'pending', 'Pending'
    COMPLETED = 'completed', 'Completed'
    NOT_APPLICABLE = 'not_applicable', 'Not Applicable'


class ActionItemFrequency(models.TextChoices):
    ONE_TIME_ONLY = '', 'One time only'
    WEEKLY = 'weekly', 'Weekly'
    MONTHLY = 'monthly', 'Monthly'
    QUARTERLY = 'quarterly', 'Quarterly'
    SEMI_ANNUALLY = 'semi_annually', 'Semi annually'
    ANNUALLY = 'annually', 'Annually'
    BI_ANNUALLY = 'bi_annually', 'Bi annually'


class ActionItemManager(models.Manager):
    @classmethod
    def create_shared_action_item(cls, users=[], steps=[], **kwargs):
        action_item = ActionItem.objects.create(steps=steps, **kwargs)
        action_item.assignees.add(*users)
        return action_item

    @classmethod
    def create_action_items(cls, users=[], steps=[], **kwargs):
        """Create an action item without assigning it to a user"""
        action_items = (
            [] if users else [ActionItem.objects.create(steps=steps, **kwargs)]
        )

        for user in users:
            action_item = ActionItem.objects.create(steps=steps, **kwargs)
            action_items.append(action_item)
            user.action_items.add(action_item)

        return action_items

    @classmethod
    def create_steps(cls, action_item, steps):
        for step in steps:
            ActionItem.objects.create_action_items(
                **step, parent_action_item=action_item
            )

    @classmethod
    def get_next_index(cls, organization, prefix='XX-C'):
        # Get the maximum name index from current action items for the org
        max_index = ActionItem.objects.filter(
            metadata__referenceId__startswith=prefix,
            controls__in=organization.controls.all(),
        ).aggregate(
            largest=models.Max(
                Cast(KeyTextTransform('referenceId', 'metadata'), models.TextField())
            )
        )[
            'largest'
        ]

        if max_index is not None:
            name_id = int(re.sub(r"[^0-9]+", "", max_index))
            name_id += 1
            return f"{prefix}-{name_id:03}"

        return f"{prefix}-001"

    def create(self, steps=[], *args, **kwargs):
        """Create an action item without assigning it to a user"""
        action_item = super(ActionItemManager, self).create(*args, **kwargs)
        self.create_steps(action_item=action_item, steps=steps)

        return action_item


@launchpad_model(context='action_item', mapper=launchpad_mapper)
class ActionItem(models.Model):
    name = models.CharField(max_length=255, blank=False)
    description = models.CharField(max_length=2048, blank=True)
    completion_date = models.DateTimeField(null=True, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    is_required = models.BooleanField(blank=True, default=False)
    is_recurrent = models.BooleanField(blank=True, default=False)
    display_id = models.IntegerField(default=9999999)
    # Format https://crontab.guru/, Length 999 because that's the standard.
    recurrent_schedule = models.CharField(
        max_length=999,
        blank=True,
        choices=ActionItemFrequency.choices,
        default=ActionItemFrequency.ONE_TIME_ONLY,
    )
    status = models.CharField(
        max_length=15, choices=ActionItemStatus.choices, default=ActionItemStatus.NEW
    )
    parent_action_item = models.ForeignKey(
        'ActionItem',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='steps',
    )
    metadata = models.JSONField(blank=True, default=dict)
    assignees = models.ManyToManyField(User, related_name="action_items")
    alerts = models.ManyToManyField(Alert, related_name="action_items")
    evidences = models.ManyToManyField('evidence.Evidence', related_name="action_items")
    tags = models.ManyToManyField(
        Tag, related_name='tags', through='ActionItemAssociatedTag'
    )

    objects = ActionItemManager()

    class Meta:
        indexes = [GinIndex(fields=['metadata'])]

    def create_action_item_alert(self, sender, receiver, alert_type, organization_id):
        return create_alert(
            room_id=organization_id,
            receiver=receiver,
            alert_type=alert_type,
            alert_related_model=self.alerts.through,
            sender=sender,
            alert_related_object={'actionitem': self},
        )

    def __str__(self):
        if self.metadata.get('referenceId'):
            return self.metadata.get('referenceId') + ' - ' + self.name
        return self.name

    def complete(self):
        self.status = ActionItemStatus.COMPLETED
        self.completion_date = now()
        self.save()

    def save(self, *args, **kwargs):
        self.is_recurrent = True if self.recurrent_schedule else False
        super(ActionItem, self).save(*args, **kwargs)

    @property
    def has_evidence(self):
        return self.evidences.count() > 0


class ActionItemTags(models.Model):
    # This is used for audit purposes to get action items evidence on fetch
    item_text = models.TextField()
    tags = models.TextField()


class ActionItemAssociatedTag(models.Model):
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    action_item = models.ForeignKey(
        ActionItem, on_delete=models.CASCADE, related_name='action_item_tags'
    )

    def __str__(self):
        return str(self.tag)
