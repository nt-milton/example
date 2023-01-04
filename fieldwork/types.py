from enum import Enum

import graphene
from django.db.models import F, Q
from graphene_django.types import DjangoObjectType

from audit.constants import AUDITOR_ROLES
from auditor.automated_testing.automated_testing import AutomatedTestingProcess
from comment.models import Comment
from comment.types import BaseCommentType, CommentType
from drive.types import DriveEvidenceType
from fieldwork.constants import CHECKLIST_AUTOMATED_TESTING_SEPARATOR, ER_TYPE
from laika.types import FileType, PaginationResponseType
from laika.utils.files import get_file_extension
from population.models import Sample
from user.types import UserType

from .models import (
    Criteria,
    CriteriaRequirement,
    Evidence,
    EvidenceComment,
    Requirement,
    RequirementComment,
    Test,
)
from .utils import (
    create_public_link,
    get_comments_count,
    get_display_id_order_annotation,
)


class EvidenceStatusEnum(Enum):
    Open = 'open'
    Submitted = 'submitted'
    AuditorAccepted = 'auditor_accepted'


evidence_status_enum = graphene.Enum.from_enum(EvidenceStatusEnum)


class EvidenceCommentPoolsEnum(Enum):
    All = 'all'
    Laika = 'laika'
    LCL = 'lcl'
    LCL_CX = 'lcl-cx'


evidence_comment_pools_enum = graphene.Enum.from_enum(EvidenceCommentPoolsEnum)


class PopulationCommentPoolsEnum(Enum):
    All = 'all'
    Laika = 'laika'
    LCL = 'lcl'
    LCL_CX = 'lcl-cx'


population_comment_pools_enum = graphene.Enum.from_enum(PopulationCommentPoolsEnum)


class EvidenceCommentType(CommentType, graphene.ObjectType):
    is_internal_comment = graphene.Boolean()
    pool = graphene.String()


class PopulationCommentType(CommentType, graphene.ObjectType):
    pool = graphene.String()


class LaikaUserAuditType(graphene.ObjectType):
    id = graphene.String()
    first_name = graphene.String()
    last_name = graphene.String()
    email = graphene.String()


class EvidenceAttachmentType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    description = graphene.String()
    file = graphene.Field(FileType)
    has_been_submitted = graphene.Boolean()
    created_at = graphene.String()
    updated_at = graphene.String()


class SampleType(DjangoObjectType):
    class Meta:
        model = Sample
        fields = ('id', 'created_at', 'updated_at')

    attachments = graphene.List(EvidenceAttachmentType)
    name = graphene.String()

    def resolve_attachments(self, info):
        attachments = self.attachments.filter(
            evidence__id=info.variable_values.get('evidenceId'), is_deleted=False
        )

        return [
            EvidenceAttachmentType(
                id=attachment.id,
                name=attachment.name,
                description=attachment.description,
                created_at=attachment.created_at,
                updated_at=attachment.updated_at,
                file=FileType(
                    id=attachment.id, name=attachment.name, url=attachment.file.url
                ),
            )
            for attachment in attachments
        ]


class RequirementEvidenceType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    display_id = graphene.String()
    attachments = graphene.List(EvidenceAttachmentType)
    status = graphene.String()


class RequirementType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    display_id = graphene.String()
    status = graphene.String()


class CriteriaType(graphene.ObjectType):
    class Meta:
        model = Criteria

    id = graphene.String()
    display_id = graphene.String()
    description = graphene.String()
    is_qualified = graphene.Boolean()


class TestType(graphene.ObjectType):
    class Meta:
        model = Test
        fields = (
            'id',
            'requirement',
        )

    id = graphene.String()
    checklist = graphene.String()
    display_id = graphene.String()
    name = graphene.String()
    notes = graphene.String()
    result = graphene.String()
    last_edited_at = graphene.String()
    is_automated = graphene.Boolean()
    automated_checklist = graphene.String()
    automated_test_result_updated_at = graphene.String()
    times_run_automate_test = graphene.Int()

    def resolve_automated_checklist(self, info):
        return f'''{self.checklist}
        {CHECKLIST_AUTOMATED_TESTING_SEPARATOR}
        {self.automated_test_result if self.automated_test_result else ""}'''

    def resolve_is_automated(self, info):
        return AutomatedTestingProcess(self).is_test_automatable()


class EvidenceRequirementType(graphene.ObjectType):
    display_id = graphene.String()
    id = graphene.String()
    name = graphene.String()
    description = graphene.String()
    result = graphene.String()
    comments_counter = graphene.Int()
    status = graphene.String()
    tester = graphene.Field(UserType)
    reviewer = graphene.Field(UserType)
    supporting_evidence = graphene.List(graphene.String)
    evidence = graphene.List(RequirementEvidenceType)
    criteria = graphene.List(CriteriaType)
    test = graphene.List(TestType)
    last_edited_at = graphene.String()

    def resolve_tester(self, info):
        return self.tester.user if self.tester else None

    def resolve_reviewer(self, info):
        return self.reviewer.user if self.reviewer else None

    def resolve_supporting_evidence(self, info):
        return [evidence.display_id for evidence in self.supporting_evidence.all()]

    def resolve_evidence(self, info):
        order_annotate = {
            'display_id_sort': get_display_id_order_annotation(preffix='ER-')
        }
        field = 'display_id_sort'

        order_query = F(field).asc(nulls_last=True)

        evidence = [
            RequirementEvidenceType(
                id=evidence.id,
                name=evidence.name,
                display_id=evidence.display_id,
                attachments=evidence.attachments,
                status=evidence.status,
            )
            for evidence in self.evidence.all()
            .annotate(**order_annotate)
            .order_by(order_query)
        ]
        return evidence

    def resolve_comments_counter(self, info):
        comments = RequirementComment.objects.filter(
            requirement__id=self.id, comment__is_deleted=False
        ).count()
        return comments

    def resolve_criteria(self, info):
        return [
            CriteriaType(
                id=criteria.id,
                display_id=criteria.display_id,
                description=criteria.description,
            )
            for criteria in self.criteria.all()
        ]

    def resolve_test(self, info):
        requirement_test = (
            Test.objects.filter(requirement=self, is_deleted=False)
            .annotate(display_id_sort=get_display_id_order_annotation(preffix='Test-'))
            .order_by('display_id_sort')
        )
        return requirement_test


class FieldworkEvidenceType(DjangoObjectType):
    class Meta:
        model = Evidence
        fields = (
            'id',
            'name',
            'display_id',
            'assignee',
            'instructions',
            'description',
            'read',
            'updated_at',
        )

    comments = graphene.List(EvidenceCommentType)
    comments_counter = graphene.Int()
    requirements = graphene.List(EvidenceRequirementType)
    attachments = graphene.List(EvidenceAttachmentType)
    status = graphene.String()
    laika_reviewed = graphene.Boolean()
    tester = graphene.Field(UserType)
    er_type = graphene.String()
    samples = graphene.List(SampleType)

    def resolve_samples(self, info):
        return Sample.objects.filter(
            evidence_request=self, population_data__isnull=False
        )

    def resolve_tester(self, info):
        first_requirement = (
            self.requirements.annotate(
                display_id_sort=get_display_id_order_annotation(preffix='LCL-')
            )
            .order_by('display_id_sort')
            .first()
        )
        return (
            first_requirement.tester.user
            if first_requirement and first_requirement.tester
            else None
        )

    def resolve_laika_reviewed(self, info):
        return self.is_laika_reviewed

    def resolve_status(self, info):
        return self.status

    def resolve_comments_counter(self, info):
        user_role = info.context.user.role
        filter_param = Q(evidence=self)
        return get_comments_count(EvidenceComment, user_role, filter_param)

    def resolve_requirements(self, info):
        requirements = [
            EvidenceRequirementType(
                id=requirement.id,
                name=requirement.name,
                display_id=requirement.display_id,
                description=requirement.description,
                supporting_evidence=requirement.evidence,
                tester=requirement.tester,
                reviewer=requirement.reviewer,
                criteria=requirement.criteria,
                last_edited_at=requirement.last_edited_at,
            )
            for requirement in self.requirements.all()
        ]

        return requirements

    def resolve_attachments(self, info):
        attachments = self.attachments
        is_sample = self.er_type == dict(ER_TYPE)['sample_er']
        should_fetch_additional_files = info.variable_values.get('isEvidenceDetail')
        organization = self.audit.organization

        if is_sample and should_fetch_additional_files:
            attachments = self.attachments.filter(sample=None, is_deleted=False)

        return [
            EvidenceAttachmentType(
                id=attachment.id,
                name=attachment.name,
                description=attachment.description,
                created_at=attachment.created_at,
                updated_at=attachment.updated_at,
                file=FileType(
                    id=attachment.id,
                    name=attachment.name,
                    url=create_public_link(attachment, organization),
                ),
                has_been_submitted=attachment.has_been_submitted,
            )
            for attachment in attachments
        ]

    def resolve_comments(self, info):
        auditor_roles = list(AUDITOR_ROLES.values())
        if info.context.user.role in auditor_roles:
            filter = Q(is_internal_comment=False) | Q(
                is_internal_comment=True, comment__owner__role__in=auditor_roles
            )
        else:
            filter = Q(is_internal_comment=False) | Q(
                Q(is_internal_comment=True) & ~Q(comment__owner__role__in=auditor_roles)
            )

        comments = []
        evidence_comment = (
            EvidenceComment.objects.filter(evidence=self)
            .filter(filter)
            .filter(comment__is_deleted=False)
            .order_by('comment__created_at')
        )
        for ev_comment in evidence_comment:
            comment = ev_comment.comment

            filtered_replies = comment.replies.filter(is_deleted=False).order_by(
                'created_at'
            )
            replies = [
                BaseCommentType(
                    id=r.id,
                    owner=r.owner,
                    owner_name=r.owner_name,
                    content=r.content,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in filtered_replies
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
                    is_internal_comment=ev_comment.is_internal_comment,
                    pool=ev_comment.pool,
                    replies=replies,
                )
            )

        return comments


class FieldworkEvidenceResponseType(graphene.ObjectType):
    evidence = graphene.List(FieldworkEvidenceType)
    pagination = graphene.Field(PaginationResponseType)


class FieldworkRequirementsResponseType(graphene.ObjectType):
    requirement = graphene.List(EvidenceRequirementType)
    pagination = graphene.Field(PaginationResponseType)


class RequirementsResponseType(graphene.ObjectType):
    requirement = graphene.List(RequirementType)


class FieldworkEvidenceAllResponseType(graphene.ObjectType):
    evidence = graphene.List(FieldworkEvidenceType)


class FieldworkFetchEvidenceResponseType(graphene.ObjectType):
    audit_id = graphene.String()


class FetchLogicEVType(graphene.ObjectType):
    evidence = graphene.List(FieldworkEvidenceType)


class AcceptedEvidenceCountType(graphene.ObjectType):
    accepted_evidence = graphene.Int()
    total_evidence = graphene.Int()


class LaikaReviewedEvidenceCountType(graphene.ObjectType):
    laika_reviewed_evidence = graphene.Int()
    total_evidence = graphene.Int()


class FieldworkDocumentsResponseType(graphene.ObjectType):
    documents = graphene.List(DriveEvidenceType)
    pagination = graphene.Field(PaginationResponseType)
    have_audit_type = graphene.Boolean()
    categories = graphene.List(graphene.String)
    audit_type = graphene.String()


def map_document_type(documents, tags_per_doc):
    attached_documents = []
    for d in documents:
        tags = [tpd['tags'] for tpd in tags_per_doc if tpd['id'] == d.evidence.id][0]
        attached_documents.append(
            DriveEvidenceType(
                id=d.evidence.id,
                name=d.evidence.name,
                created_at=d.evidence.created_at,
                updated_at=d.evidence.updated_at,
                evidence_type=d.evidence.type,
                owner=d.owner,
                extension=get_file_extension(d.evidence.file.name),
                tags=tags,
                description=d.evidence.description,
                file=d.evidence.file,
            )
        )

    return attached_documents


class FieldworkCriteriaType(DjangoObjectType):
    class Meta:
        model = Criteria

    id = graphene.String()
    display_id = graphene.String()
    description = graphene.String()


class FieldworkCriteriaRequirementType(DjangoObjectType):
    class Meta:
        model = CriteriaRequirement

    id = graphene.String()
    criteria = graphene.Field(FieldworkCriteriaType)
    requirements = graphene.List(EvidenceRequirementType)

    def resolve_requirements(self, info):
        return self.criteria.requirements.all().filter(
            audit_id=self.requirement.audit.id, is_deleted=False
        )


class FieldworkCriteriaResponseType(graphene.ObjectType):
    criteria_requirement = graphene.List(FieldworkCriteriaRequirementType)
    pagination = graphene.Field(PaginationResponseType)


class RequirementCommentType(BaseCommentType, graphene.ObjectType):
    class Meta:
        model = Comment

    replies = graphene.List(BaseCommentType)

    def resolve_replies(self, info):
        return self.replies.all().filter(is_deleted=False).order_by('created_at')


# TODO: FZ-1892: Below this point, only new types are going to be create
# so we can slowly deprecate old types and code


class RequirementTestType(DjangoObjectType):
    class Meta:
        model = Test
        fields = ('id', 'name', 'result')


class AuditSimplifiedEvidenceType(DjangoObjectType):
    class Meta:
        model = Evidence
        fields = ('id', 'display_id')


class AuditRequirementType(DjangoObjectType):
    class Meta:
        model = Requirement
        fields = ('id', 'name', 'display_id', 'status', 'description')

    evidence = graphene.List(AuditSimplifiedEvidenceType)
    tests = graphene.List(RequirementTestType)

    def resolve_evidence(self, info):
        return self.evidence.filter(is_deleted=False)

    def resolve_tests(self, info):
        return self.tests.filter(is_deleted=False)


class AuditCriteriaType(DjangoObjectType):
    class Meta:
        model = Criteria
        fields = ('id', 'display_id', 'description', 'is_qualified')

    requirements = graphene.List(AuditRequirementType)

    def resolve_requirements(self, info):
        audit_id = info.variable_values.get('auditId')
        return self.requirements.filter(audit_id=audit_id, is_deleted=False)


class CriteriaPaginatedResponseType(graphene.ObjectType):
    criteria = graphene.List(AuditCriteriaType)
    pagination = graphene.Field(PaginationResponseType)
