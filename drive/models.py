import enum
import uuid
from dataclasses import dataclass, field
from typing import List

from django.core.files import File
from django.db import models

import evidence.constants as constants
from drive.tasks import refresh_drive_cache
from drive.utils import launchpad_mapper
from evidence.evidence_handler import (
    create_officer_pdf_evidence,
    create_team_pdf_evidence,
)
from evidence.models import (
    Evidence,
    SystemTagEvidence,
    SystemTagLegacyEvidence,
    TagEvidence,
)
from organization.models import Organization
from program.models import SubTask, SubtaskTag
from search.search import launchpad_model
from tag.models import Tag
from user.models import Team, User


class OwnerOrderBy(enum.Enum):
    FIELD = 'owner'
    FIRST_NAME = 'owner__first_name'
    LAST_NAME = 'owner__last_name'


class TagsOrderBy(enum.Enum):
    FIELD = 'tags'


class DaysOrderBy(enum.Enum):
    FIELD = 'time'
    FILTERS = [('LAST_SEVEN_DAYS', 7), ('LAST_MONTH', 30), ('LAST_QUARTER', 120)]


class CertificatesOrderBy(enum.Enum):
    FIELD = 'certificates'


class PlaybooksOrderBy(enum.Enum):
    FIELD = 'playbooks'


def get_unlocked_subtasks_per_task(task):
    cache_name = (
        f'unlocked_subtasks_for_task_{task.id}_organization_'
        f'{task.program.organization.id}'
    )
    subtasks = task.get_unlocked_subtasks(cache_name=cache_name)
    return subtasks


@launchpad_model(context='document', mapper=launchpad_mapper)
class Drive(models.Model):
    organization = models.OneToOneField(
        Organization, on_delete=models.CASCADE, related_name='drive'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'drives'

    def __str__(self):
        return self.organization.name

    @property
    def last_updated_evidence(self):
        return self.evidence.all().latest(
            'evidence__updated_at', '-evidence__created_at'
        )


class Folder(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=512)
    drive = models.ForeignKey(Drive, related_name='folders', on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.drive.organization.name} - {self.name}'


@dataclass
class DriveEvidenceData:
    type: str
    file: File
    is_template: bool = False
    tags: List[Tag] = field(default_factory=lambda: [])
    system_tags: List[Tag] = field(default_factory=lambda: [])
    system_tags_legacy: List[Tag] = field(default_factory=lambda: [])


class DriveEvidenceQuerySet(models.QuerySet):
    def sort(self, order_by):
        all_evidence = self.all()

        if not all_evidence.exists():
            return all_evidence

        if not order_by:
            return all_evidence.order_by('-evidence__updated_at')

        if order_by.get('field') == OwnerOrderBy.FIELD.value:
            order_by_owner = OwnerOrderBy.FIRST_NAME.value
            order_by_owner = (
                '-' + order_by_owner
                if order_by.get('order') == 'descend'
                else order_by_owner
            )
            return all_evidence.order_by(order_by_owner, OwnerOrderBy.LAST_NAME.value)

        org = self.first().evidence.organization
        evidence_in_drive = Evidence.objects.filter(
            organization=org, type__in=[constants.FILE, constants.LAIKA_PAPER]
        )
        return all_evidence.order_by(evidence_in_drive.sort(order_by))

    def filter_by_certs(self, cert_filter):
        docs = []
        for d in self.all():
            if cert_filter in d.evidence.certificate_tags:
                docs.append(d)

        return docs


class DriveEvidenceManager(models.Manager):
    _queryset_class = DriveEvidenceQuerySet

    def custom_create(self, organization, owner, drive_evidence_data, filters={}):
        if not filters:
            filters = {'drive': organization.drive}

        evidence = Evidence.objects.custom_create(
            organization=organization,
            upload_file=drive_evidence_data.file,
            evidence_type=drive_evidence_data.type,
            reference_model=DriveEvidence,
            filters=filters,
        )

        for tag in drive_evidence_data.tags:
            TagEvidence.objects.create(tag=tag, evidence=evidence)

        for tag in drive_evidence_data.system_tags:
            SystemTagEvidence.objects.create(tag=tag, evidence=evidence)

        for tag in drive_evidence_data.system_tags_legacy:
            SystemTagLegacyEvidence.objects.get_or_create(tag=tag, evidence=evidence)

        return super().create(
            drive=organization.drive,
            evidence=evidence,
            owner=owner,
            is_template=drive_evidence_data.is_template,
        )

    def custom_create_teams(self, organization, time_zone, tags, teams, user):
        ids = []
        for team_id in teams:
            team = Team.objects.get(organization=organization, id=team_id)
            team_pdf, _ = create_team_pdf_evidence(team, time_zone)
            self.custom_create_file(organization, ids, team_pdf, tags, user)
        return ids

    def custom_create_officers(self, organization, time_zone, tags, officers, user):
        ids = []
        officers_pdf, _ = create_officer_pdf_evidence(organization, officers, time_zone)
        if officers_pdf:
            self.custom_create_file(organization, ids, officers_pdf, tags, user)
        return ids

    def custom_create_file(self, organization, ids, pdf_file, tags, user):
        drive_evidence_data = DriveEvidenceData(
            type=constants.FILE, file=pdf_file, **tags
        )
        drive_evidence = self.custom_create(
            organization=organization,
            owner=user,
            drive_evidence_data=drive_evidence_data,
        )
        ids.append(drive_evidence.evidence.id)

    @property
    def evidence_tags(self):
        all_tags = []
        for de in self.all():
            for t in de.evidence.tags.all().order_by('name'):
                all_tags.append(t)
        return all_tags

    @property
    def system_tags(self):
        all_subtasks_system_tags = []
        for de in self.all():
            subtask_system_tags = SystemTagEvidence.objects.filter(evidence=de.evidence)
            for st in subtask_system_tags:
                subtask_tags = SubtaskTag.objects.filter(
                    subtask__id=st.tag.name, tag__organization=de.evidence.organization
                )
                all_subtasks_system_tags.extend(
                    [
                        stt.tag
                        for stt in subtask_tags
                        if stt.subtask
                        in get_unlocked_subtasks_per_task(stt.subtask.task)
                    ]
                )
        return all_subtasks_system_tags

    @property
    def evidence_and_system_tags(self):
        tags = set(
            [t.name for t in self.evidence_tags] + [st.name for st in self.system_tags]
        )
        return sorted(tags)

    @staticmethod
    def subtasks_with_tag(organization, tag_name):
        subtasks_with_metadata = []
        subtask_tags = SubtaskTag.objects.filter(
            tag__name=tag_name, tag__organization=organization
        )
        # Subtasks with the given tag
        for st in subtask_tags:
            subtasks_with_metadata.append(st.subtask.id)

        # Get the ids of subtasks that have any
        # evidence related so that we can look for the
        # related subtask and their tags
        tags = Tag.objects.filter(
            id__in=SystemTagEvidence.objects.filter(
                evidence_id__in=Evidence.objects.filter(
                    organization=organization
                ).values_list('id', flat=True)
            ).values_list('tag_id', flat=True)
        ).values_list('name', flat=True)
        subtasks_ids = [uuid.UUID(tag) for tag in tags]
        subtasks_with_evidence = SubTask.objects.filter(
            task__program__organization=organization, id__in=subtasks_ids
        )
        for subtask in subtasks_with_evidence:
            if tag_name in subtask.metadata_tags:
                subtasks_with_metadata.append(subtask.id)

        return subtasks_with_metadata


class DriveEvidence(models.Model):
    drive = models.ForeignKey(
        Drive, on_delete=models.CASCADE, related_name='evidence', null=True, blank=True
    )
    folder = models.ForeignKey(
        Folder, on_delete=models.CASCADE, related_name='evidence', null=True, blank=True
    )
    evidence = models.ForeignKey(
        Evidence, on_delete=models.CASCADE, related_name='drive'
    )
    owner = models.ForeignKey(
        User,
        related_name='owned_evidence',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_template = models.BooleanField(default=False)

    objects = DriveEvidenceManager()

    def save(self, *args, **kwargs):
        refresh_drive_cache.delay(self.drive.organization.id, [self.evidence.id])
        super(DriveEvidence, self).save(*args, **kwargs)

    def __str__(self):
        return self.evidence.name
