import io
import logging
import uuid
import zipfile
from multiprocessing.pool import ThreadPool

import django.utils.timezone as timezone
from django.db import models
from django.db.models import Q
from django.http import HttpResponse
from django.utils.functional import cached_property

from action_item.models import ActionItem
from alert.models import Alert
from certification.models import Certification, CertificationSection
from comment.models import Comment
from evidence import constants
from evidence.models import EVIDENCE_TYPE, Evidence, evidence_upload_directory
from feature.constants import playbooks_feature_flag
from laika.cache import cache_func
from laika.constants import CATEGORIES
from laika.storage import PrivateMediaStorage
from laika.utils.zip import zip_file
from organization.models import Organization
from program.constants import (
    GETTING_STARTED_TIER,
    SUBTASK_COMPLETED_STATUS,
    SUBTASK_GROUP,
    SUBTASK_PRIORITIES,
    SUBTASK_STATUS,
    TASK_TIERS,
)
from program.utils.alerts import create_alert
from search.search import searchable_model
from tag.models import Tag
from user.models import User

from .utils.hadle_cache import trigger_program_cache
from .utils.program_progress import get_program_progress

logger = logging.getLogger('Program')

pool = ThreadPool()

PRIORITY_CERTS = ['GDPR', 'ISO 27001', 'PCI DSS v3.2', 'SOC 2 Type 1', 'SOC 2 Type 2']


class Program(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='programs'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(max_length=1024)
    sort_index = models.IntegerField(default=9999999, null=True, blank=True)
    documentation_link = models.TextField(blank=True)
    program_lead = models.ForeignKey(
        User,
        related_name='program_led',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    static_icon = models.CharField(max_length=255, blank=True)
    animated_icon = models.CharField(max_length=255, blank=True)

    @cached_property
    def has_tasks(self):
        return self.tasks.all().count() > 0

    @property
    def unlocked_subtasks(self):
        if self.has_tasks:
            first, *others = self.tasks.all()
            cache_name = (
                'unlocked_subtasks_for_task_'
                f'{first.id}_organization_'
                f'{self.organization.id}'
            )
            qs = first.get_unlocked_subtasks(cache_name=cache_name)
            for t in others:
                cache_name = (
                    'unlocked_subtasks_for_task_'
                    f'{t.id}_organization_'
                    f'{self.organization.id}'
                )
                qs = qs.union(t.get_unlocked_subtasks(cache_name=cache_name))
            return qs
        # self.tasks.all() is empty then returns empty query set
        return self.tasks.all()

    @property
    def user_subtasks(self):
        if self.has_tasks:
            first, *others = self.tasks.all()
            qs = first.user_subtasks.all()
            for t in others:
                qs = qs.union(t.user_subtasks)
            return qs
        # self.tasks.all() is empty then returns empty query set
        return self.tasks.all()

    @property
    def visible_subtasks(self):
        if self.unlocked_subtasks or self.user_subtasks:
            return self.unlocked_subtasks.union(self.user_subtasks)
        else:
            SubTask.objects.none()

    @property
    def completed_visible_subtasks(self):
        if self.has_tasks:
            first, *others = self.tasks.all()
            qs = first.completed_visible_subtasks.all()
            for t in others:
                qs = qs.union(t.completed_visible_subtasks)
            return qs
        # self.tasks.all() is empty then returns empty query set
        return self.tasks.all()

    @property
    def all_subtasks(self):
        if self.has_tasks:
            first, *others = self.tasks.all()
            qs = first.all_subtasks.all()
            for t in others:
                qs = qs.union(t.all_subtasks.all())
            return qs
        # self.tasks.all() is empty then returns empty query set
        return self.tasks.all()

    @property
    def progress(self):
        if (
            self.visible_subtasks is None
            or self.visible_subtasks.count() == 0
            or self.completed_visible_subtasks.count() == 0
        ):
            return 0

        return (
            self.completed_visible_subtasks.count()
            / self.visible_subtasks.count()
            * 100
        )

    @property
    def progress_reloaded(self):
        cache_name = f'program_progress_{self.id}_organization_{self.organization.id}'
        progress, *_ = get_program_progress(self, SubTask, cache_name=cache_name)
        return progress

    @property
    def is_locked(self):
        certificate_ids = self.unlocked_certificate_ids
        return not SubTask.objects.filter(
            task__program=self,
            certification_sections__certification_id__in=certificate_ids,
        ).exists()

    @property
    def unlocked_certificates(self):
        return self.organization.unlocked_and_archived_unlocked_certs

    @cached_property
    def unlocked_certificate_ids(self):
        return list(
            self.unlocked_certificates.values_list('certification_id', flat=True)
        )

    @cache_func
    def get_all_certificates(self, **kwargs):
        unlocked_certificates = []
        locked_certificates = []
        certification_sections = []
        if self.all_subtasks:
            certification_sections = self.all_subtasks.values_list(
                'certification_sections', flat=True
            )
        certificates = (
            Certification.objects.filter(
                sections__in=CertificationSection.objects.filter(
                    id__in=certification_sections
                ).distinct()
            )
            .distinct()
            .order_by('name')
        )

        for c in certificates:
            if c.id in self.unlocked_certificate_ids:
                unlocked_certificates.append(c)
            else:
                locked_certificates.append(c)

        priority_certs = [c for c in locked_certificates if c.name in PRIORITY_CERTS]

        # Get some specific certs at the beginning
        for idx, c in enumerate(priority_certs):
            c_i = locked_certificates.index(c)
            locked_certificates[idx], locked_certificates[c_i] = (
                locked_certificates[c_i],
                locked_certificates[idx],
            )

        unlocked_certificates.extend(locked_certificates)
        return unlocked_certificates

    @property
    def visible_tasks(self):
        return [t for t in self.tasks.all() if t.is_visible]

    @cache_func
    def get_visible_tasks(self, **kwargs):
        return [t for t in self.tasks.all() if t.is_visible]

    def save(self, *args, **kwargs):
        super(Program, self).save()

        if not kwargs.get('no_cache'):
            trigger_program_cache.delay(self.organization.id)

    def __str__(self):
        return self.name


def howto_guide_upload_directory(instance, filename):
    return f'{instance.program.organization.id}/tasks/{instance.id}/howto/{filename}'


#   TODO: Remove this one once legacy programs goes away
def filter_tasks(user, model):
    organization = user.organization
    is_playbook_enabled = organization.is_flag_active(playbooks_feature_flag)

    if not is_playbook_enabled:
        return model.objects.none()

    return model.objects.filter(program__organization=organization)


def task_qs(user, model):
    organization = user.organization

    return model.objects.filter(
        program_id__in=(organization.programs.all().values('id'))
    )


@searchable_model(
    type='task',
    qs=task_qs,
)
class Task(models.Model):
    class Meta:
        permissions = [
            (
                'change_task_implementation_notes',
                'Can change task implementation notes',
            ),
            ('add_task_comment', 'Can add task comment'),
            ('change_task_comment', 'Can change task comment'),
            ('delete_task_comment', 'Can delete task comment'),
            ('view_task_comment', 'Can view task comment'),
        ]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name='tasks',
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    implementation_notes = models.TextField(blank=True, default='')
    category = models.CharField(
        max_length=255, choices=CATEGORIES, blank=False, default='Other'
    )
    how_to_guide = models.JSONField(default=list, null=True, blank=True)
    tier = models.CharField(
        max_length=255, choices=TASK_TIERS, default=GETTING_STARTED_TIER
    )
    overview = models.TextField(blank=True, default='')

    comments = models.ManyToManyField(
        Comment, related_name='tasks', through='TaskComment'
    )

    number = models.IntegerField(default=0)
    customer_identifier = models.CharField(max_length=50, blank=False, default='')

    @property
    def unlocked_certificates(self):
        return self.program.organization.unlocked_and_archived_unlocked_certs.values(
            'certification_id'
        )

    @cache_func
    def get_all_unlocked_subtasks(self, **kwargs):
        unlocked_ids = (
            self.program.organization.unlocked_and_archived_unlocked_certs.values(
                'certification_id'
            )
        )

        return self.all_subtasks.filter(
            certification_sections__certification_id__in=unlocked_ids
        ).distinct()

    @property
    def unlocked_subtasks_complexity_groups(self):
        cache_name = (
            f'all_unlocked_subtasks_for_task_{self.id}'
            f'_organization_{self.program.organization.id}'
        )
        all_unlocked_subtasks = self.get_all_unlocked_subtasks(cache_name=cache_name)
        complexity_groups = (
            all_unlocked_subtasks.exclude(complexity_group__isnull=True)
            .exclude(complexity_group__exact='')
            .values('complexity_group')
            .distinct()
            .order_by('complexity_group')
        )

        return complexity_groups.all().values_list('complexity_group', flat=True)

    @property
    def excluded_subtasks_ids_by_complexity(self):
        subtasks_ids_to_exclude = []
        cache_name = (
            f'all_unlocked_subtasks_for_task_{self.id}'
            f'_organization_{self.program.organization.id}'
        )
        all_unlocked_subtasks = self.get_all_unlocked_subtasks(cache_name=cache_name)
        for cg in self.unlocked_subtasks_complexity_groups:
            subtasks_by_complexity_group = (
                all_unlocked_subtasks.filter(
                    complexity_group=cg,
                )
                .exclude(complexity_group__isnull=True)
                .exclude(complexity_group__exact='')
                .order_by('-complexity')
            )
            highest_complexity_subtask = subtasks_by_complexity_group.first()
            subtasks_to_exclude = subtasks_by_complexity_group.exclude(
                id=highest_complexity_subtask.id,
            )
            for s in subtasks_to_exclude:
                # subtasks with evidence should be shown even if complexity is
                # lower than highest_complexity_subtask
                if not s.has_evidence:
                    subtasks_ids_to_exclude.append(s.id)
        return subtasks_ids_to_exclude

    @cache_func
    def get_unlocked_subtasks(self, **kwargs):
        unlocked_ids = (
            self.program.organization.unlocked_and_archived_unlocked_certs.values(
                'certification_id'
            )
        )

        return (
            self.all_subtasks.filter(
                certification_sections__certification_id__in=unlocked_ids
            )
            .exclude(id__in=self.excluded_subtasks_ids_by_complexity)
            .distinct()
        )

    @property
    def user_subtasks(self):
        return self.all_subtasks.filter(is_system_subtask=False).distinct()

    @property
    def visible_subtasks(self):
        cache_name = (
            f'unlocked_subtasks_for_task_{self.id}_organization_'
            f'{self.program.organization.id}'
        )
        unlocked_subtasks = self.get_unlocked_subtasks(cache_name=cache_name)
        return unlocked_subtasks.union(self.user_subtasks)

    @property
    def completed_visible_subtasks(self):
        cache_name = (
            f'unlocked_subtasks_for_task_{self.id}_organization_'
            f'{self.program.organization.id}'
        )
        unlocked_subtasks = self.get_unlocked_subtasks(cache_name=cache_name)
        completed_unlocked_subtasks = unlocked_subtasks.filter(
            status=SUBTASK_COMPLETED_STATUS
        )
        completed_user_subtasks = self.user_subtasks.filter(
            status=SUBTASK_COMPLETED_STATUS
        )
        return completed_unlocked_subtasks.union(completed_user_subtasks)

    @property
    def progress(self):
        if self.visible_subtasks.count():
            return (
                self.completed_visible_subtasks.count()
                / self.visible_subtasks.count()
                * 100
            )

        return 0

    @property
    def is_visible(self):
        cache_name = (
            f'unlocked_subtasks_for_task_{self.id}_organization_'
            f'{self.program.organization.id}'
        )
        unlocked_subtasks = self.get_unlocked_subtasks(cache_name=cache_name)
        return unlocked_subtasks.exists()

    def __str__(self):
        return self.name


class SubTask(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    reference_id = models.UUIDField(blank=True, null=True)
    migration_id = models.CharField(max_length=1024, blank=True, default='')
    text = models.TextField()
    assignee = models.ForeignKey(
        User,
        related_name='subtask_assignee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    group = models.CharField(
        max_length=100, choices=SUBTASK_GROUP, blank=False, default=None
    )
    requires_evidence = models.BooleanField(default=False)
    sort_index = models.IntegerField(default=9999999, null=True, blank=True)
    tags = models.ManyToManyField(Tag, related_name='subtasks', through='SubtaskTag')
    badges = models.CharField(max_length=255, blank=True, default='')

    certification_sections = models.ManyToManyField(
        CertificationSection,
        related_name='subtasks',
        through='SubtaskCertificationSection',
    )

    status = models.CharField(
        max_length=50, choices=SUBTASK_STATUS, blank=False, default='not_started'
    )

    priority = models.CharField(
        max_length=50, choices=SUBTASK_PRIORITIES, blank=False, default='required'
    )
    due_date = models.DateField(blank=True, null=True)
    completed_on = models.DateField(blank=True, null=True)

    task = models.ForeignKey(
        Task,
        related_name='all_subtasks',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    complexity_group = models.CharField(max_length=50, blank=True, default='')

    complexity = models.IntegerField(
        null=True,
        blank=True,
    )

    number = models.IntegerField(default=0)
    customer_identifier = models.CharField(max_length=50, blank=False, default='')

    action_item = models.ForeignKey(
        ActionItem,
        related_name='subtasks',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    @property
    def evidence(self):
        drive_evidence = self.task.program.organization.drive.evidence.filter(
            evidence__system_tags__name=str(self.id)
        ).values_list('evidence_id', flat=True)
        evidence_drive = Evidence.objects.filter(id__in=drive_evidence)
        evidence_linked = Evidence.objects.filter(
            system_tags__in=Tag.objects.filter(name=str(self.id))
        )
        return evidence_drive.union(evidence_linked)

    @property
    def has_evidence(self):
        return self.evidence.count() > 0

    is_system_subtask = models.BooleanField(default=True)

    @property
    def related_subtasks(self):
        cache_name = (
            f'all_unlocked_subtasks_for_task_{self.task.id}'
            f'_organization_{self.task.program.organization.id}'
        )
        all_unlocked_subtasks = self.task.get_all_unlocked_subtasks(
            cache_name=cache_name
        )
        subtasks = (
            all_unlocked_subtasks.filter(
                complexity_group=self.complexity_group,
            )
            .exclude(Q(complexity_group__isnull=True) & Q(complexity_group__exact=''))
            .order_by('-complexity')
        )

        if not subtasks:
            return []

        related_subtasks = []
        if self.id == subtasks.first().id:
            related_subtasks = subtasks.exclude(id=self.id)
        return related_subtasks

    @property
    def related_subtasks_tags(self):
        all_tags = []
        for related_subtask in self.related_subtasks:
            tags = [t.name for t in related_subtask.tags.all()]
            all_tags.extend(tags)
        return all_tags

    @property
    def playbook_tag(self):
        return self.task.program.name

    @property
    def certificates_tags(self):
        unlock_certificates = self.task.program.unlocked_certificates.all()
        unlock_certificates_ids = Certification.objects.filter(
            id__in=unlock_certificates.values_list('certification_id', flat=True)
        )
        certificate_sections = self.certification_sections.filter(
            certification__in=unlock_certificates_ids
        )
        certificates_names = [
            section.certification.name for section in certificate_sections
        ]
        return certificates_names

    @property
    def related_subtasks_playbooks(self):
        playbooks = []
        for related_subtask in self.related_subtasks:
            playbooks.append(related_subtask.playbook_tag)
        return playbooks

    @property
    def related_subtasks_certificates(self):
        certificates = []
        for related_subtask in self.related_subtasks:
            certificates.extend(related_subtask.certificates_tags)
        return certificates

    @property
    def metadata_tags(self):
        metadata_tags = [self.playbook_tag]
        certificates_tags = self.certificates_tags
        metadata_tags.extend(certificates_tags)
        if self.related_subtasks:
            metadata_tags.extend(
                self.related_subtasks_playbooks
                + self.related_subtasks_certificates
                + self.related_subtasks_tags
            )
        return list(set(metadata_tags))

    class Meta:
        permissions = [('change_subtask_partial', 'Can change subtask partially')]
        ordering = ('sort_index',)

    def __str__(self):
        return self.text[:100]

    def get_text(self):
        return self.text[:100] + '...'

    def get_priority(self):
        return self.get_priority_display()

    get_priority.short_description = 'Priority'  # type: ignore

    def get_group(self):
        return self.get_group_display()

    get_group.short_description = 'Group'  # type: ignore

    def _increment_sort_index(self):
        # Get the maximum sort_index value from the database
        last_id = SubTask.objects.filter(task=self.task).aggregate(
            largest=models.Max('sort_index')
        )['largest']

        if last_id is not None:
            self.sort_index = last_id + 1

    def create_subtask_alert(self, alert_type, sender):
        create_alert(
            room_id=self.task.program.organization.id,
            sender=sender,
            receiver=self.assignee,
            alert_type=alert_type,
            alert_related_model=SubtaskAlert,
            alert_related_object={'subtask': self},
        )

    def get_tags_for_evidence(self, organization):
        system_tag, _ = Tag.objects.get_or_create(
            organization=organization, name=str(self.id)
        )

        tag_category, _ = Tag.objects.get_or_create(
            organization=organization, name=str(self.task.category)
        )

        subtask_tags = self.tags.all()

        tags = {'tags': [tag_category], 'system_tags': [system_tag]}
        for tag in subtask_tags:
            tags['tags'].append(tag)

        return tags

    def save(self, *args, **kwargs):
        if self._state.adding:
            self._increment_sort_index()
        super(SubTask, self).save(*args, **kwargs)


class TaskCommentManager(models.Manager):
    def custom_create(
        self, organization, owner, content, task_id, tagged_users, subtask_id=None
    ):
        comment = Comment.objects.create(owner=owner, content=content)

        task = Task.objects.get(program__organization=organization, id=task_id)

        subtask = None
        if subtask_id:
            subtask = SubTask.objects.get(id=subtask_id, task=task)

        task_comment = super().create(task=task, comment=comment, subtask=subtask)

        mentions = comment.add_mentions(tagged_users)
        if mentions:
            for mention in mentions:
                room_id = mention.user.organization.id
                alert = mention.create_mention_alert(room_id)
                if alert:
                    task_related = mention.get_mention_task_related()
                    alert.send_comment_task_alert_email(task_related=task_related)

        return task_comment.comment


class TaskComment(models.Model):
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, related_name='task_comments'
    )
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='task')
    # This is for the case a subtask is linked on a task comment
    subtask = models.ForeignKey(
        SubTask,
        on_delete=models.CASCADE,
        related_name='comments',
        null=True,
        blank=True,
    )

    objects = TaskCommentManager()


class SubtaskTag(models.Model):
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    subtask = models.ForeignKey(
        SubTask,
        on_delete=models.CASCADE,
    )

    class Meta:
        verbose_name_plural = 'tags'

    def __str__(self):
        return self.tag.name


class SubtaskCertificationSection(models.Model):
    certification_section = models.ForeignKey(
        CertificationSection, on_delete=models.CASCADE
    )

    subtask = models.ForeignKey(
        SubTask,
        on_delete=models.CASCADE,
    )

    class Meta:
        verbose_name_plural = 'certification_sections'

    def __str__(self):
        return self.certification_section.name


class SubtaskAlert(models.Model):
    alert = models.ForeignKey(
        Alert, related_name='subtask_alert', on_delete=models.CASCADE
    )
    subtask = models.ForeignKey(
        SubTask,
        related_name='subtask',
        on_delete=models.CASCADE,
    )


#
# Archived Programs, Tasks, Subtasks and Evidence Models
#


class ArchivedProgram(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    data = models.JSONField()
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='archived_program'
    )

    def __str__(self):
        return str(self.id)


class ArchivedTask(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    data = models.JSONField()
    program = models.ForeignKey(
        ArchivedProgram,
        on_delete=models.CASCADE,
        related_name='tasks',
        null=True,
        blank=True,
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='archived_task'
    )

    def __str__(self):
        return str(self.id)


class ArchivedSubtask(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    data = models.JSONField()
    task = models.ForeignKey(
        ArchivedTask, on_delete=models.CASCADE, related_name='subtasks'
    )

    def __str__(self):
        return str(self.id)


class ArchivedEvidenceQuerySet(models.QuerySet):
    def export(self):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zf:
            for current in self:
                if current.type != constants.FILE:
                    logger.warning(
                        f'Invalid type {current.type} '
                        f'for evidence id {current.id} '
                        f'with organization: {current.organization}'
                    )
                    return HttpResponse('Invalid type', status=404)
                zip_file(current, zf)
        zip_buffer.seek(0)
        return zip_buffer


class ArchivedEvidenceManager(models.Manager):
    _queryset_class = ArchivedEvidenceQuerySet


class ArchivedUser(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    first_name = models.CharField(max_length=150, null=True, blank=True)
    last_name = models.CharField(max_length=150, null=True, blank=True)
    email = models.CharField(max_length=150)

    class Meta:
        verbose_name_plural = 'archived users'

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


class ArchivedEvidence(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=512)
    description = models.TextField(blank=True)
    file = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=evidence_upload_directory,
        max_length=1024,
        null=True,
        blank=True,
    )
    type = models.CharField(max_length=20, choices=EVIDENCE_TYPE, blank=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='archived_evidence'
    )
    archived_task = models.ForeignKey(
        ArchivedTask, on_delete=models.CASCADE, related_name='archived_evidence'
    )
    legacy_evidence = models.ForeignKey(
        Evidence,
        on_delete=models.SET_NULL,
        related_name='archived_evidence',
        blank=True,
        null=True,
    )
    owner = models.ForeignKey(
        ArchivedUser,
        related_name='archived_evidence',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    objects = ArchivedEvidenceManager()

    class Meta:
        verbose_name_plural = 'archived evidence'

    def __str__(self):
        return f'Archived Evidence name: {self.name}, type: {self.type}'
