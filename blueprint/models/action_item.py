from django.db import models
from tinymce.models import HTMLField

from action_item.models import ActionItemFrequency, ActionItemStatus
from blueprint.choices import SuggestedOwner

from .tag import TagBlueprint


class ActionItemBlueprint(models.Model):
    class Meta:
        verbose_name_plural = 'Action Items Blueprint'

    reference_id = models.CharField(unique=True, max_length=255)
    airtable_record_id = models.CharField(blank=True, max_length=512)
    name = models.CharField(unique=True, max_length=255)
    description = HTMLField()
    is_required = models.BooleanField(default=False)
    is_recurrent = models.BooleanField(default=False)
    requires_evidence = models.BooleanField(default=False)
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
    suggested_owner = models.CharField(
        max_length=50,
        null=True,
        choices=SuggestedOwner.choices,
    )
    metadata = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField()

    tags = models.ManyToManyField(
        TagBlueprint, related_name='action_items', through='ActionItemBlueprintTag'
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.is_recurrent = True if self.recurrent_schedule else False
        super(ActionItemBlueprint, self).save(*args, **kwargs)


class ActionItemBlueprintTag(models.Model):
    tag = models.ForeignKey(TagBlueprint, on_delete=models.CASCADE)
    action_item = models.ForeignKey(
        ActionItemBlueprint, on_delete=models.CASCADE, related_name='action_item_tags'
    )

    def __str__(self):
        return str(self.tag)
