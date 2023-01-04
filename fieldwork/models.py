import logging
from typing import List

import django.utils.timezone as timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.files import File
from django.db import models
from django.db.models import QuerySet

import evidence.constants as constants
import fieldwork.util as utils
from alert.constants import ALERT_TYPES
from alert.models import Alert
from audit.models import Audit
from certification.models import Certification
from comment.models import Comment
from fieldwork.launchpad import launchpad_mapper
from laika.constants import WS_AUDITOR_GROUP_NAME
from laika.storage import PrivateMediaStorage
from laika.utils.exceptions import ServiceException
from laika.utils.increment_file_name import increment_file_name
from policy.models import Policy
from search.search import launchpad_model
from training.models import Training
from user.constants import AUDITOR, AUDITOR_ADMIN, AUDITOR_ROLES
from user.models import Auditor, Team, User

from .constants import (
    ACCOUNT_LAIKA_OBJECT_RUN_OPTIONS,
    COMMENTS_POOLS,
    COMMENTS_POOLS_DICT,
    DOCUMENT_FETCH_TYPE,
    ER_TYPE,
    EVIDENCE_STATUS,
    OTHER_SOURCE_TYPE,
    POLICY_FETCH_TYPE,
    REQUIREMENT_RESULTS,
    REQUIREMENT_STATUS,
    TEAM_FETCH_TYPE,
    TEST_RESULTS,
    TRAINING_FETCH_TYPE,
)

logger = logging.getLogger('fieldwork_models')


def attachment_upload_directory(instance, filename):
    organization_id = instance.evidence.audit.organization.id
    audit_id = instance.evidence.audit.id
    return f'{organization_id}/{audit_id}/{instance.evidence.id}/attachment/{filename}'


def tmp_attachment_upload_directory(instance, filename):
    organization_id = instance.audit.organization.id
    audit_id = instance.audit.id
    return f'{organization_id}/{audit_id}/tmp_attachment/{filename}'


def get_room_id_for_alerts(receiver):
    is_auditor = AUDITOR_ROLES['AUDITOR'] in receiver.role
    return WS_AUDITOR_GROUP_NAME if is_auditor else receiver.organization.id


def create_evidence_mention_alerts(mentions):
    for mention in mentions:
        room_id = get_room_id_for_alerts(mention.user)
        alert = mention.create_mention_alert(room_id, ALERT_TYPES['EVIDENCE_MENTION'])
        if alert:
            if mention.comment:
                evidence = mention.comment.evidence_comments.first().evidence
                content = mention.comment.content
            else:
                evidence = mention.reply.parent.evidence_comments.first().evidence
                content = mention.reply.content
            alert.send_evidence_comment_alert_email(
                evidence=evidence,
                content=content,
            )


def create_mention_alerts(mentions):
    for mention in mentions:
        room_id = get_room_id_for_alerts(mention.user)
        mention.create_mention_alert(room_id, ALERT_TYPES['REQUIREMENT_MENTION'])


class FetchLogic(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    audit = models.ForeignKey(
        Audit, related_name='fetch_logic', on_delete=models.CASCADE, null=True
    )
    code = models.CharField(
        max_length=50, blank=True, default=''
    )  # had to allow blank values for existing rows
    type = models.CharField(max_length=50)
    logic = models.JSONField()
    description = models.TextField(null=True, blank=True)

    def __str__(self):
        return f'{self.code}'


class EvidenceManager(models.Manager):
    def not_deleted_evidence(self, kwargs):
        return (
            super()
            .get_queryset()
            .filter(
                audit__id=kwargs.get('audit_id'),
                is_deleted=False,
            )
        )


@launchpad_model(context='evidence_request', mapper=launchpad_mapper)
class Evidence(models.Model):
    class Meta:
        unique_together = (('display_id', 'audit'),)
        verbose_name_plural = 'Evidence Request'
        constraints = [
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_valid_er_type",
                check=models.Q(er_type__in=[er_type[0] for er_type in ER_TYPE]),
            )
        ]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    audit = models.ForeignKey(Audit, related_name='evidence', on_delete=models.CASCADE)
    display_id = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    instructions = models.TextField()
    description = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=EVIDENCE_STATUS, default='open')
    assignee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name='assignee_ev',
        null=True,
        blank=True,
    )
    # If the ev has being opened for review
    read = models.BooleanField(default=False)
    comments = models.ManyToManyField(
        Comment, related_name='evidence', through='EvidenceComment'
    )
    fetch_logic = models.ManyToManyField(
        FetchLogic, related_name='evidence', through='EvidenceFetchLogic'
    )
    is_deleted = models.BooleanField(default=False)

    is_laika_reviewed = models.BooleanField(default=False)

    times_moved_back_to_open = models.IntegerField(default=0)

    is_fetch_logic_accurate = models.BooleanField(default=False)

    run_account_lo_fetch = models.CharField(
        max_length=50, choices=ACCOUNT_LAIKA_OBJECT_RUN_OPTIONS, default='run'
    )
    er_type = models.CharField(
        max_length=50, choices=ER_TYPE, default='evidence_request'
    )

    def __str__(self):
        return f'{self.display_id} {self.name}'

    @property
    def attachments(self):
        return Attachment.objects.filter(
            evidence__id=self.id, is_deleted=False
        ).order_by('created_at')

    def delete_attachment(self, name):
        attachment = Attachment.objects.filter(
            evidence__id=self.id,
            is_deleted=False,
            from_fetch=True,
            has_been_submitted=False,
            name=name,
        ).first()
        if attachment:
            attachment.is_deleted = True
            attachment.save()

    def add_attachment(
        self,
        file_name,
        policy=None,
        file=None,
        is_from_fetch=False,
        attach_type=OTHER_SOURCE_TYPE,
        origin_source_object=None,
    ):
        from policy.views import get_published_policy_pdf

        file_name_exists = Attachment.objects.filter(
            name=file_name, evidence=self, is_deleted=False
        )

        if file_name_exists and is_from_fetch:
            self.delete_attachment(name=file_name)

        upload_name = (
            increment_file_name(
                filters={'evidence': self, 'is_deleted': False},
                reference_model=Attachment,
                file_name=file_name,
            )
            if file_name_exists
            else file_name
        )
        attachment = None
        source = utils.evidence_attachment.get_attachment_source_type(attach_type)

        if policy and file is None:
            published_policy_file = get_published_policy_pdf(policy.id)
            if published_policy_file:
                attachment = Attachment.objects.create(
                    evidence=self,
                    name=upload_name,
                    file=File(name=file_name, file=published_policy_file),
                    from_fetch=is_from_fetch,
                    source=source,
                    origin_source_object=origin_source_object,
                )
        else:
            attachment = Attachment.objects.create(
                evidence=self,
                name=upload_name,
                file=file,
                from_fetch=is_from_fetch,
                source=source,
                origin_source_object=origin_source_object,
            )
        return attachment

    def get_comments(self, pool: str) -> List:
        from comment.types import BaseCommentType
        from fieldwork.types import EvidenceCommentType

        comments = []
        evidence_comments = self.comments.filter(
            evidence_comments__pool=pool, is_deleted=False
        ).order_by('created_at')
        for comment in evidence_comments:
            evidence_comment = comment.evidence_comments.first()
            filtered_replies = comment.replies.filter(is_deleted=False).order_by(
                'created_at'
            )
            replies = [
                BaseCommentType(
                    id=reply.id,
                    owner=reply.owner,
                    owner_name=reply.owner_name,
                    content=reply.content,
                    created_at=reply.created_at,
                    updated_at=reply.updated_at,
                )
                for reply in filtered_replies
            ]
            comments.append(
                EvidenceCommentType(
                    id=comment.id,
                    owner=comment.owner,
                    owner_name=comment.owner_name,
                    content=comment.content,
                    created_at=comment.created_at,
                    updated_at=comment.updated_at,
                    is_deleted=comment.is_deleted,
                    state=comment.state,
                    is_internal_comment=evidence_comment.is_internal_comment,
                    pool=evidence_comment.pool,
                    replies=replies,
                )
            )

        return comments

    objects = EvidenceManager()

    def delete(self, *args, **kwargs):
        comments = Comment.objects.filter(evidence_comments__evidence=self)
        Alert.objects.filter(
            comment_alert__comment__evidence_comments__evidence=self
        ).delete()
        Alert.objects.filter(reply_alert__reply__parent__in=comments).delete()

        super(Evidence, self).delete(*args, **kwargs)


class EvidenceMetric(models.Model):
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['evidence_request'], name='unique_evidence_request'
            ),
        ]

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    evidence_request = models.ForeignKey(
        Evidence, on_delete=models.CASCADE, related_name='metrics'
    )
    integrations_counter = models.JSONField(blank=True, null=True)
    monitors_count = models.IntegerField(default=0)


class EvidenceStatusTransition(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    evidence = models.ForeignKey(
        Evidence, on_delete=models.CASCADE, related_name='status_transitions'
    )
    transitioned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='er_status_transitions', null=True
    )
    laika_reviewed = models.BooleanField(default=False)
    from_status = models.CharField(
        max_length=50,
        choices=EVIDENCE_STATUS,
    )
    to_status = models.CharField(
        max_length=50,
        choices=EVIDENCE_STATUS,
    )
    transition_reasons = models.CharField(max_length=200, blank=True, default='')
    extra_notes = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.from_status == self.to_status:
            return
        super(EvidenceStatusTransition, self).save(*args, **kwargs)


# Creating a table for this because basically we can have more
# types added later, so to be able to do it from django if necessary


class AttachmentSourceType(models.Model):
    class Meta:
        constraints = [models.UniqueConstraint(fields=['name'], name='unique_name')]

    name = models.CharField(max_length=50, default=OTHER_SOURCE_TYPE)
    template = models.JSONField(
        blank=True, default=dict, verbose_name='Automated source template'
    )

    def __str__(self):
        return self.name


class Attachment(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=512)
    description = models.TextField(blank=True)
    evidence = models.ForeignKey(
        Evidence, on_delete=models.CASCADE, related_name='attachment'
    )
    source = models.ForeignKey(
        AttachmentSourceType,
        on_delete=models.SET_NULL,
        related_name='attachments',
        blank=True,
        null=True,
    )
    deleted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='deleted_er_attachment', null=True
    )
    file = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=attachment_upload_directory,
        max_length=1024,
        null=True,
        blank=True,
    )

    is_deleted = models.BooleanField(default=False, null=True)

    from_fetch = models.BooleanField(default=False, null=True)
    sample = models.ForeignKey(
        'population.Sample',
        on_delete=models.SET_NULL,
        related_name='attachments',
        blank=True,
        null=True,
    )
    has_been_submitted = models.BooleanField(default=False)

    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    object_id = models.CharField(max_length=40, blank=True, null=True)
    origin_source_object = GenericForeignKey('content_type', 'object_id')

    def rename(self, attachment_input):
        from evidence.evidence_handler import get_strip_file_name

        stripped_name = get_strip_file_name(constants.FILE, attachment_input.new_name)

        if len(stripped_name) > constants.DOCUMENT_NAME_MAX_LENGHT:
            raise ServiceException('Attachment name is too long.')

        name_exists = Attachment.objects.filter(
            evidence_id=attachment_input.evidence_id,
            name=stripped_name,
            is_deleted=False,
        ).exists()

        if name_exists:
            raise ServiceException(
                'This file name already exists. Use a different name.'
            )

        self.name = stripped_name
        self.save()


class TemporalAttachment(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    fetch_logic = models.ForeignKey(
        FetchLogic,
        related_name='fl_tmp_attachment',
        on_delete=models.CASCADE,
        null=True,
    )

    audit = models.ForeignKey(
        Audit, related_name='audit_tmp_attachment', on_delete=models.CASCADE
    )

    policy = models.ForeignKey(
        Policy, related_name='policy', on_delete=models.CASCADE, null=True
    )

    document = models.ForeignKey(
        "evidence.Evidence",
        related_name='document',
        on_delete=models.CASCADE,
        null=True,
    )

    training = models.ForeignKey(
        Training, related_name='training', on_delete=models.CASCADE, null=True
    )

    team = models.ForeignKey(
        Team, related_name='team', on_delete=models.CASCADE, null=True
    )

    name = models.CharField(max_length=512, null=True)

    file = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=tmp_attachment_upload_directory,
        max_length=1024,
        null=True,
        blank=True,
    )


class EvidenceCommentManager(models.Manager):
    def custom_create(
        self,
        owner,
        content,
        evidence_id,
        tagged_users,
        is_internal_comment=None,
        pool=None,
    ):
        comment = Comment.objects.create(owner=owner, content=content)

        evidence = Evidence.objects.get(
            pk=evidence_id,
        )

        evidence_comment_data = {
            'evidence': evidence,
            'comment': comment,
        }
        if is_internal_comment:
            evidence_comment_data['is_internal_comment'] = True
            if owner.role in [AUDITOR_ADMIN, AUDITOR]:
                evidence_comment_data['pool'] = COMMENTS_POOLS_DICT['LCL']
            else:
                evidence_comment_data['pool'] = COMMENTS_POOLS_DICT['Laika']

        else:
            evidence_comment_data['pool'] = COMMENTS_POOLS_DICT['All']

        if pool:
            evidence_comment_data['pool'] = pool

        evidence_comment = super().create(**evidence_comment_data)

        mentions = comment.add_mentions(tagged_users)
        create_evidence_mention_alerts(mentions)

        return evidence_comment.comment


class EvidenceComment(models.Model):
    evidence = models.ForeignKey(
        Evidence, on_delete=models.CASCADE, related_name='evidence_comments'
    )
    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, related_name='evidence_comments'
    )
    is_internal_comment = models.BooleanField(default=False)
    pool = models.CharField(max_length=10, choices=COMMENTS_POOLS, null=True)

    objects = EvidenceCommentManager()


class EvidenceFetchLogic(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    evidence = models.ForeignKey(
        Evidence, related_name='ev_fetch_logic', on_delete=models.CASCADE
    )
    fetch_logic = models.ForeignKey(
        FetchLogic, related_name='ev_fetch_logic', on_delete=models.CASCADE
    )


class Criteria(models.Model):
    class Meta:
        unique_together = (('display_id', 'audit'),)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    display_id = models.CharField(max_length=50)
    description = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    audit = models.ForeignKey(
        Audit, related_name='criteria', on_delete=models.CASCADE, null=True, blank=True
    )
    is_qualified = models.BooleanField(default=False)

    @property
    def audit_types(self):
        criteria_types = self.criteria_audit_types.all()
        return [ct.type.name for ct in criteria_types]

    def __str__(self):
        return f'{self.display_id}'


class CriteriaAuditType(models.Model):
    criteria = models.ForeignKey(
        Criteria, related_name='criteria_audit_types', on_delete=models.CASCADE
    )
    type = models.ForeignKey(Certification, on_delete=models.CASCADE)


class RequirementEvidenceManager(models.Manager):
    def custom_create(
        self,
        display_id: str,
        audit_id: str,
        evidence: QuerySet[Evidence],
        name: str,
        description: str,
    ):
        requirement = super().create(
            display_id=display_id, audit_id=audit_id, name=name, description=description
        )
        for er in evidence:
            RequirementEvidence.objects.create(evidence=er, requirement=requirement)
        return requirement


class Requirement(models.Model):
    class Meta:
        unique_together = (('display_id', 'audit'),)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    audit = models.ForeignKey(
        Audit, related_name='requirements', on_delete=models.CASCADE
    )
    display_id = models.CharField(max_length=50)
    name = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=50, choices=REQUIREMENT_STATUS, default='open')
    tester = models.ForeignKey(
        Auditor,
        related_name='tester_requirements',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    tester_updated_at = models.DateTimeField(null=True, blank=True)
    reviewer = models.ForeignKey(
        Auditor,
        related_name='reviewer_requirements',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    reviewer_updated_at = models.DateTimeField(null=True, blank=True)
    result = models.CharField(
        max_length=50, choices=REQUIREMENT_RESULTS, null=True, blank=True
    )
    result_exception_note = models.TextField(blank=True, null=True, default='')
    result_comment = models.TextField(blank=True, null=True, default='')
    evidence = models.ManyToManyField(
        Evidence, related_name='requirements', through='RequirementEvidence'
    )
    is_deleted = models.BooleanField(default=False)
    criteria = models.ManyToManyField(
        'Criteria', related_name='requirements', through='CriteriaRequirement'
    )
    exclude_in_report = models.BooleanField(default=False)
    times_moved_back_to_open = models.IntegerField(default=0)

    objects = RequirementEvidenceManager()

    last_edited_at = models.DateTimeField(blank=True, null=True)
    last_edited_by = models.ForeignKey(
        User,
        related_name='fieldwork_requirement',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f'{self.display_id} {self.name}'

    def delete(self, *args, **kwargs):
        comments = Comment.objects.filter(requirement_comments__requirement=self)
        Alert.objects.filter(
            comment_alert__comment__requirement_comments__requirement=self
        ).delete()
        Alert.objects.filter(reply_alert__reply__parent__in=comments).delete()

        super(Requirement, self).delete(*args, **kwargs)


class Test(models.Model):
    class Meta:
        unique_together = (('display_id', 'requirement'),)
        constraints = [
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_valid_test_result",
                check=models.Q(
                    result__in=[test_result[0] for test_result in TEST_RESULTS]
                ),
            )
        ]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    display_id = models.CharField(max_length=50)
    name = models.TextField()
    checklist = models.TextField()
    result = models.CharField(max_length=100, choices=TEST_RESULTS, null=True)
    notes = models.TextField(null=True, blank=True)
    requirement = models.ForeignKey(
        Requirement,
        related_name='tests',
        on_delete=models.CASCADE,
    )
    is_deleted = models.BooleanField(default=False)
    last_edited_at = models.DateTimeField(blank=True, null=True)
    last_edited_by = models.ForeignKey(
        User,
        related_name='fieldwork_test',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    automated_test_result = models.TextField(null=True, blank=True, default=None)
    automated_test_result_updated_at = models.DateTimeField(
        null=True, blank=True, default=None
    )
    times_run_automate_test = models.IntegerField(default=0)


class RequirementEvidence(models.Model):
    class Meta:
        unique_together = (('evidence', 'requirement'),)

    evidence = models.ForeignKey(
        Evidence, related_name='requirement_ev', on_delete=models.CASCADE
    )
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE)


class CriteriaRequirement(models.Model):
    class Meta:
        unique_together = (('criteria', 'requirement'),)

    criteria = models.ForeignKey(
        Criteria, related_name='criteria_requirement', on_delete=models.CASCADE
    )
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE)


class EVFetchLogicFilter:
    def __init__(self, organization, evidence, results, fetch_logic):
        self.evidence = evidence
        self.organization = organization
        self.results = results
        self.fetch_logic = fetch_logic

    def add_evidence_attachment(self, tmp_attachment, origin_source_object=None):
        if tmp_attachment:
            self.evidence.add_attachment(
                file_name=tmp_attachment.name,
                file=tmp_attachment.file,
                is_from_fetch=True,
                attach_type=self.fetch_logic.type,
                origin_source_object=origin_source_object,
            )

    def run_policy_query(self):
        policies = Policy.objects.filter(
            organization=self.organization, name__in=self.results
        ).distinct()
        for policy in policies:
            tmp_attachment = TemporalAttachment.objects.filter(policy=policy).first()
            self.add_evidence_attachment(tmp_attachment, origin_source_object=policy)

    def run_document_query(self):
        from evidence.models import Evidence as Document

        documents = Document.objects.filter(
            organization=self.organization, name__in=self.results
        )
        for ev in documents:
            tmp_attachment = TemporalAttachment.objects.filter(document=ev).first()
            self.add_evidence_attachment(tmp_attachment, origin_source_object=ev)

    def run_training_query(self):
        trainings = Training.objects.filter(
            organization=self.organization, name__in=self.results
        )
        for training in trainings:
            tmp_attachment = TemporalAttachment.objects.filter(
                training=training
            ).first()
            self.add_evidence_attachment(tmp_attachment, origin_source_object=training)

    def run_team_query(self):
        teams = Team.objects.filter(
            organization=self.organization, name__in=self.results
        )
        for team in teams:
            tmp_attachment = TemporalAttachment.objects.filter(team=team).first()
            self.add_evidence_attachment(tmp_attachment, origin_source_object=team)

    def run_filter_query(self):
        if self.fetch_logic.type == POLICY_FETCH_TYPE:
            self.run_policy_query()

        if self.fetch_logic.type == DOCUMENT_FETCH_TYPE:
            self.run_document_query()

        if self.fetch_logic.type == TRAINING_FETCH_TYPE:
            self.run_training_query()

        if self.fetch_logic.type == TEAM_FETCH_TYPE:
            self.run_team_query()


class RequirementCommentManager(models.Manager):
    def custom_create(
        self,
        owner,
        content,
        requirement_id,
        tagged_users,
    ):
        comment = Comment.objects.create(owner=owner, content=content)

        requirement = Requirement.objects.get(
            pk=requirement_id,
        )

        requirement_comment_data = {
            'requirement': requirement,
            'comment': comment,
        }

        requirement_comment = super().create(**requirement_comment_data)

        mentions = comment.add_mentions(tagged_users)
        create_mention_alerts(mentions)

        return requirement_comment.comment


class RequirementComment(models.Model):
    requirement = models.ForeignKey(
        Requirement, on_delete=models.CASCADE, related_name='requirement_comments'
    )
    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, related_name='requirement_comments'
    )

    objects = RequirementCommentManager()


class EvidenceRequestAttachment:
    def __init__(
        self,
        id,
        name,
        evidence_type,
        owner,
        created_at,
        updated_at,
        extension,
        tags,
        description,
        file,
    ):
        self.id = id
        self.name = name
        self.evidence_type = evidence_type
        self.owner = owner
        self.created_at = created_at
        self.updated_at = updated_at
        self.extension = extension
        self.tags = tags
        self.description = description
        self.file = file


class RequirementStatusTransition(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    requirement = models.ForeignKey(
        Requirement, on_delete=models.CASCADE, related_name='status_transitions'
    )
    from_status = models.CharField(
        max_length=50,
        choices=REQUIREMENT_STATUS,
    )
    to_status = models.CharField(
        max_length=50,
        choices=REQUIREMENT_STATUS,
    )

    status_updated_by = models.ForeignKey(
        User,
        related_name='requirement_status_transitions',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    def save(self, *args, **kwargs):
        if self.from_status == self.to_status:
            return
        super(RequirementStatusTransition, self).save(*args, **kwargs)
