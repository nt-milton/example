import logging
import re
import uuid
from typing import List

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import F, Func, IntegerField, Value
from django.db.models.aggregates import Count
from django.db.models.functions import Cast
from django.utils import timezone

from action_item.models import ActionItem
from alert.constants import ALERT_TYPES
from alert.models import Alert
from blueprint.models import ImplementationGuideBlueprint
from certification.models import CertificationSection
from comment.models import Comment, Reply
from evidence.models import Evidence
from feature.constants import new_controls_feature_flag
from laika.constants import CATEGORIES, FREQUENCIES
from laika.storage import PublicMediaStorage
from organization.models import Organization
from policy.models import Policy
from search.search import launchpad_model
from tag.models import Tag
from user.helpers import get_user_by_email
from user.models import User

from .constants import CONTROLS_MONITORS_HEALTH as HEALTH
from .constants import (
    CUSTOM_PREFIX,
    MAX_OWNER_LIMIT_PER_CONTROL,
    MONITOR_INSTANCE_STATUS_TRIGGERED,
    STATUS,
)
from .helpers import controls_health_map_cache, fill_max_owners
from .utils.launchpad import launchpad_mapper

logger = logging.getLogger(__name__)


class RoadMap(models.Model):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='roadmap'
    )

    def __str__(self) -> str:
        return f'{self.organization}'


class ControlsQuerySet(models.QuerySet):
    def delete(self, *args, **kwargs):
        controls = self

        for control in controls:
            control.delete()

        super(ControlsQuerySet, self).delete(*args, **kwargs)

    def migrate_to_custom(self) -> List[str]:
        status_detail = []
        for control in self:
            control._increment_reference_id()
            control.save()

            message = f'Control {control.reference_id} migrated successfully'
            status_detail.append(message)
            logger.info(message)
        return status_detail


@launchpad_model(context='control', mapper=launchpad_mapper)
class Control(models.Model):
    class Meta:
        permissions = [
            ('batch_delete_control', 'Can batch delete controls'),
            ('change_control_status', 'Can change control status'),
            ('associate_user', 'Can associate user to control'),
            ('add_control_evidence', 'Can add control evidence'),
            ('delete_control_evidence', 'Can delete control evidence'),
            ('can_migrate_to_my_compliance', 'Can migrate to my compliance'),
        ]

    objects = ControlsQuerySet.as_manager()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    implementation_date = models.DateTimeField(null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='controls'
    )
    display_id = models.IntegerField(default=9999999)
    reference_id = models.CharField(max_length=50, blank=True, null=True)
    household = models.CharField(null=True, blank=True, max_length=100)
    name = models.TextField(blank=False, default=None)
    # Setting these as nullable because as there can be rows already
    # it doesn't let me create it without a default.
    administrator = models.ForeignKey(
        User, related_name='control_admin', on_delete=models.SET_NULL, null=True
    )
    owner1 = models.ForeignKey(
        User, related_name='control_owner', on_delete=models.SET_NULL, null=True
    )
    owner2 = models.ForeignKey(
        User, related_name='control_owner1', on_delete=models.SET_NULL, null=True
    )
    owner3 = models.ForeignKey(
        User, related_name='control_owner2', on_delete=models.SET_NULL, null=True
    )
    approver = models.ForeignKey(
        User, related_name='control_approver', on_delete=models.SET_NULL, null=True
    )
    description = models.TextField(blank=True, default='')
    category = models.CharField(max_length=200, choices=CATEGORIES, blank=True)
    frequency = models.CharField(max_length=50, choices=FREQUENCIES, blank=True)
    implementation_guide_blueprint = models.ForeignKey(
        ImplementationGuideBlueprint,
        null=True,
        related_name='linked_controls',
        on_delete=models.SET_NULL,
    )
    implementation_notes = models.TextField(blank=True, default='')
    status = models.CharField(max_length=30, blank=True)
    policies = models.ManyToManyField(
        Policy, related_name='controls', through='ControlPolicy'
    )
    tags = models.ManyToManyField(Tag, related_name='controls', through='ControlTag')

    certification_sections = models.ManyToManyField(
        CertificationSection,
        related_name='controls',
        through='ControlCertificationSection',
    )

    evidence = models.ManyToManyField(
        Evidence, related_name='controls', through='ControlEvidence'
    )

    pillar = models.ForeignKey(
        'ControlPillar', null=True, related_name='control', on_delete=models.SET_NULL
    )

    comments = models.ManyToManyField(
        Comment, related_name='control', through='ControlComment'
    )

    action_items = models.ManyToManyField(ActionItem, related_name='controls')

    has_new_action_items = models.BooleanField(default=False, blank=True, null=True)

    framework_tag = models.CharField(blank=True, max_length=512)

    def __str__(self):
        if self.reference_id:
            return self.reference_id + ' - ' + self.name
        return self.name

    @property
    def owners(self):
        return [
            getattr(self, f'owner{owner_index + 1}')
            for owner_index in range(MAX_OWNER_LIMIT_PER_CONTROL)
            if getattr(self, f'owner{owner_index + 1}') is not None
        ]

    @owners.setter
    def owners(self, emails):
        emails_filled_up = fill_max_owners(emails)

        for index, email in enumerate(emails_filled_up):
            if email:
                owner = get_user_by_email(
                    organization_id=self.organization_id, email=email
                )
            else:
                owner = email
            setattr(self, f'owner{index + 1}', owner)

    def _increment_display_id(self):
        # Get the maximum display_id value from the database
        last_id = Control.objects.filter(organization=self.organization).aggregate(
            largest=models.Max('display_id')
        )['largest']

        if last_id is not None:
            self.display_id = last_id + 1

    def _numbers_only_max_reference_id(self):
        # Get the maximum reference_id index from current controls
        # the annotation cleans the XX- and leaves just the number
        max_reference_id = (
            Control.objects.filter(
                reference_id__startswith=CUSTOM_PREFIX, organization=self.organization
            )
            .annotate(
                ref_num=Cast(
                    Func(
                        F('reference_id'),
                        Value(r'\d+'),
                        function='regexp_matches',
                    ),
                    output_field=ArrayField(IntegerField()),
                ),
            )
            .aggregate(largest=models.Max('ref_num'))['largest']
        )

        # the regexp_matches returns a list
        return max_reference_id[0]

    def _increment_reference_id(self):
        max_index_num = 0
        max_reference_id = Control.objects.filter(
            reference_id__startswith=CUSTOM_PREFIX, organization=self.organization
        ).aggregate(largest=models.Max('reference_id'))['largest']

        if max_reference_id:
            max_index_num = int(re.sub(r"[^0-9]+", "", max_reference_id))
            if max_index_num == 99:
                # reference_id is a string, so XX-99 is greater than XX-100
                # _numbers_only_max_reference_id can handle that, but
                # it cannot be tested in SQLite
                max_index_num = self._numbers_only_max_reference_id()

        name_id = max_index_num + 1
        self.reference_id = f"{CUSTOM_PREFIX}-{name_id:02}"

    def save(self, *args, **kwargs):
        if self._state.adding:
            self._increment_display_id()
            if self.reference_id is None:
                # delete this flag feature when ControlActionItems are released
                new_controls_ff = self.organization.is_flag_active(
                    new_controls_feature_flag
                )
                if new_controls_ff:
                    self._increment_reference_id()

        super(Control, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        action_items_with_control_count = ActionItem.objects.select_related().annotate(
            controls_count=Count('controls__pk')
        )

        action_items_related_only_current_control = (
            action_items_with_control_count.filter(
                controls__id=self.id, controls_count=1
            )
        )

        Alert.objects.filter(
            action_items__in=action_items_related_only_current_control
        ).delete()

        action_items_related_only_current_control.delete()

        action_items_without_control = action_items_with_control_count.filter(
            metadata__organizationId=str(self.organization.id), controls_count=0
        )

        action_items_without_control.delete()

        comments = self.comments.all()

        Alert.objects.filter(reply_alert__reply__parent__in=comments).delete()
        Alert.objects.filter(comment_alert__comment__in=comments).delete()
        Reply.objects.filter(parent__in=comments).delete()
        comments.delete()

        super(Control, self).delete(*args, **kwargs)

    @property
    def health(self):
        if self.status.upper() == STATUS['NOT IMPLEMENTED']:
            return HEALTH['NOT_IMPLEMENTED']

        monitor_status_count = (
            self.organization_monitors.filter(active=True)
            .values_list('status')
            .annotate(count=Count('status'))
        )

        monitor_statuses = dict(monitor_status_count)
        total_monitors = sum(monitor_statuses.values())
        monitors_triggered = monitor_statuses.get('triggered', 0) > 0
        monitors_no_datasource = monitor_statuses.get('no_datasource', 0) > 0

        # delete this flag feature when ControlActionItems are released.
        new_controls_ff = self.organization.is_flag_active(new_controls_feature_flag)

        if new_controls_ff:
            today = timezone.now()
            expired_action_items_count = self.action_items.filter(
                status='new', due_date__lte=today
            ).count()

            if (
                monitors_triggered
                or monitors_no_datasource
                or expired_action_items_count
            ):
                return HEALTH['FLAGGED']

            return HEALTH['HEALTHY']
        # delete this else when new health with action items is release
        else:
            all_monitors_healthy = (
                monitor_statuses.get('healthy', 0) == total_monitors
                and total_monitors > 0
            )

            if not monitor_status_count:
                return HEALTH['NO_MONITORS']

            if monitors_triggered:
                return HEALTH['FLAGGED']

            if all_monitors_healthy:
                return HEALTH['HEALTHY']

            return HEALTH['NO_DATA']

    @property
    def position(self):
        total_controls_with_reference_id = Control.objects.filter(
            organization=self.organization, reference_id__isnull=False
        ).count()
        if self.reference_id:
            reference_id_controls_position = (
                Control.objects.filter(
                    organization=self.organization,
                    reference_id__isnull=False,
                    reference_id__lte=self.reference_id,
                )
                .order_by('reference_id')
                .count()
            )
        display_id_controls_position = (
            Control.objects.filter(
                organization=self.organization,
                reference_id__isnull=True,
                display_id__lte=self.display_id,
            )
            .order_by('display_id')
            .count()
            + total_controls_with_reference_id
        )

        return (
            reference_id_controls_position
            if self.reference_id
            else display_id_controls_position
        )

    @property
    def next(self):
        if self.reference_id:
            next_control = (
                Control.objects.filter(
                    organization=self.organization, reference_id__gt=self.reference_id
                )
                .order_by('reference_id')
                .first()
            )
            if not next_control:
                next_control = (
                    Control.objects.filter(
                        organization=self.organization, reference_id__isnull=True
                    )
                    .order_by('display_id')
                    .first()
                )
        else:
            next_control = (
                Control.objects.filter(
                    organization=self.organization, display_id__gt=self.display_id
                )
                .exclude(reference_id__isnull=False)
                .order_by('display_id')
                .first()
            )

        return next_control

    @property
    def previous(self):
        if self.reference_id:
            previous_control = (
                Control.objects.filter(
                    organization=self.organization, reference_id__lt=self.reference_id
                )
                .order_by('-reference_id')
                .first()
            )
        else:
            previous_control = (
                Control.objects.filter(
                    organization=self.organization, display_id__lt=self.display_id
                )
                .order_by('-display_id')
                .first()
            )
            if not previous_control:
                previous_control = (
                    Control.objects.filter(organization=self.organization)
                    .exclude(reference_id__isnull=True)
                    .order_by('-reference_id')
                    .first()
                )

        return previous_control

    @property
    def flaggedMonitors(self):
        return self.organization_monitors.filter(
            active=True, status=MONITOR_INSTANCE_STATUS_TRIGGERED
        ).count()

    @staticmethod
    def controls_health(organization_id, refresh_cache=False):
        organization_controls = Control.objects.filter(organization_id=organization_id)

        return controls_health_map_cache(
            organization_controls,
            cache_name=f"controls_health_{organization_id}",
            time_out=60,
            force_update=refresh_cache,
        )


class ControlGroup(models.Model):
    roadmap = models.ForeignKey(
        RoadMap, on_delete=models.CASCADE, related_name='groups'
    )
    name = models.CharField(max_length=255)
    reference_id = models.CharField(max_length=50, blank=True, null=True)
    controls = models.ManyToManyField(Control, related_name='group')
    start_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    sort_order = models.IntegerField()

    def _increment_sort_order(self, roadmap: RoadMap):
        FIRST_SORT_ORDER = 1

        last_sort_order = ControlGroup.objects.filter(
            roadmap_id=self.roadmap.id
        ).aggregate(largest=models.Max('sort_order'))['largest']

        self.sort_order = (last_sort_order + 1) if last_sort_order else FIRST_SORT_ORDER

    def save(self, *args, **kwargs):
        if self._state.adding and not self.sort_order:
            self._increment_sort_order(self.roadmap)

        super(ControlGroup, self).save(*args, **kwargs)

    def __str__(self) -> str:
        return f'{self.name}'


class ControlTag(models.Model):
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    control = models.ForeignKey(
        Control, on_delete=models.CASCADE, related_name='control_tags'
    )

    def __str__(self):
        return str(self.tag)


class ControlPolicy(models.Model):
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE)
    control = models.ForeignKey(
        Control, on_delete=models.CASCADE, related_name='control_policies'
    )

    def __str__(self):
        return str(self.policy)


class ControlCertificationSection(models.Model):
    certification_section = models.ForeignKey(
        CertificationSection, on_delete=models.CASCADE
    )

    control = models.ForeignKey(
        Control,
        on_delete=models.CASCADE,
    )

    def __str__(self):
        return str(self.certification_section)


class ControlEvidence(models.Model):
    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE)
    control = models.ForeignKey(Control, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.evidence)


def pillar_illustration_directory_path(instance, filename):
    return f'pillar/{instance.name}/{filename}'


class ControlPillar(models.Model):
    name = models.CharField(unique=True, max_length=255)
    acronym = models.CharField(max_length=20, blank=True, null=True)

    description = models.CharField(blank=True, max_length=255)

    illustration = models.FileField(
        storage=PublicMediaStorage(),
        max_length=1024,
        upload_to=pillar_illustration_directory_path,
        blank=True,
    )

    @property
    def full_name(self):
        if self.acronym:
            return f"{self.acronym}: {self.name}"
        return self.name

    def __str__(self):
        return self.name


class ControlCommentManager(models.Manager):
    def custom_create(self, organization, owner, content, control_id, tagged_users):
        comment = Comment.objects.create(owner=owner, content=content)

        control = Control.objects.get(organization=organization, id=control_id)

        control_comment = super().create(control=control, comment=comment)

        mentions = comment.add_mentions(tagged_users)
        if mentions:
            for mention in mentions:
                room_id = mention.user.organization.id
                alert = mention.create_mention_alert(
                    room_id, ALERT_TYPES['CONTROL_MENTION']
                )
                if alert:
                    control_related = mention.get_mention_control_related()
                    alert.send_comment_control_alert_email(
                        control_related=control_related
                    )
        return control_comment.comment


class ControlComment(models.Model):
    control = models.ForeignKey(
        Control, on_delete=models.CASCADE, related_name='control_comments'
    )
    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, related_name='control_comments'
    )

    objects = ControlCommentManager()
