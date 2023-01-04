import graphene
from graphene_django.types import DjangoObjectType

from certification.types import CertificateType
from comment.types import BaseCommentType, CommentType
from laika.utils.files import get_file_extension
from monitor.types import OrganizationMonitorType
from program.constants import (
    SUBTAKS_IMPLEMENTATION,
    SUBTASK_DOCUMENTATION,
    SUBTASK_GROUP,
    SUBTASK_POLICY,
    SUBTASK_PRIORITIES,
    SUBTASK_STATUS,
    TASK_TIERS,
)
from program.models import (
    ArchivedEvidence,
    ArchivedSubtask,
    ArchivedTask,
    ArchivedUser,
    Program,
    SubTask,
    Task,
)
from user.types import UserType


class StatusType(graphene.ObjectType):
    id = graphene.String()
    done = graphene.Int(default_value=0)
    total = graphene.Int(default_value=0)


class ArchivedProgramType(graphene.ObjectType):
    id = graphene.UUID(required=True)
    data = graphene.JSONString()


class ResourceType(graphene.ObjectType):
    id = graphene.Int(required=True)
    name = graphene.String(required=True)
    description = graphene.String(required=True)
    link = graphene.String(required=True)
    resource_type = graphene.String(required=True, name='type')
    tags = graphene.List(graphene.String)


class SubTaskAssigneeType(graphene.ObjectType):
    id = graphene.UUID(required=True)
    assignee_email = graphene.String(required=True)


class SubTaskEvidenceType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    description = graphene.String()
    link = graphene.String()
    type = graphene.String()
    date = graphene.DateTime()
    system_tag_created_at = graphene.DateTime()


class MonitorReferenceType(graphene.ObjectType):
    id = graphene.String()
    flag = graphene.String()
    organization_monitors = graphene.List(OrganizationMonitorType)


class SubTaskType(DjangoObjectType):
    class Meta:
        model = SubTask
        fields = (
            'created_at',
            'updated_at',
            'id',
            'text',
            'assignee',
            'group',
            'requires_evidence',
            'sort_index',
            'certification_sections',
            'status',
            'due_date',
        )

    badges = graphene.List(graphene.String)
    status = graphene.String()
    tags = graphene.List(graphene.String)
    priority = graphene.String()
    group = graphene.String()
    evidence = graphene.List(SubTaskEvidenceType)
    task = graphene.String()
    certifications = graphene.List(graphene.String)
    customer_number = graphene.String()
    monitor_reference = graphene.Field(MonitorReferenceType)

    def resolve_monitor_reference(self, info):
        if not self.reference_id:
            return None
        monitor_loader = info.context.loaders.monitor
        return monitor_loader.monitor_subtask.load(self.reference_id).then(
            lambda r: MonitorReferenceType(self.id, *r)
        )

    def resolve_badges(self, info):
        if not self.badges:
            return []
        badges_str = self.badges.split(',')
        return set(badges_str)

    def resolve_status(self, info):
        d = dict(SUBTASK_STATUS)
        return d[self.status]

    def resolve_priority(self, info):
        d = dict(SUBTASK_PRIORITIES)
        return d[self.priority]

    def resolve_group(self, info):
        d = dict(SUBTASK_GROUP)
        return d[self.group]

    def resolve_evidence(self, info):
        evidence = []
        for e in self.evidence:
            link = ''
            system_tag_created_at = (
                e.systemtagevidence_set.filter(tag__name=str(self.id))
                .order_by('-created_at')
                .first()
                .created_at
            )
            # Policies do not have file object
            if e.file:
                link = e.file.url
            evidence.append(
                SubTaskEvidenceType(
                    id=e.id,
                    name=e.name,
                    link=link,
                    description=e.description,
                    date=e.created_at,
                    type=e.type,
                    system_tag_created_at=system_tag_created_at,
                )
            )
        return sorted(evidence, key=lambda x: x.system_tag_created_at, reverse=True)

    def resolve_task(self, info):
        return self.task.id

    def resolve_certifications(self, info):
        return self.certificates_tags

    def resolve_customer_number(self, info):
        return self.customer_identifier


class SubTaskGroupType(graphene.ObjectType):
    id = graphene.Int(required=True)
    name = graphene.String()
    subtasks = graphene.List(SubTaskType)

    def resolve_name(self, info):
        d = dict(SUBTASK_GROUP)
        return d[self.name]


class TaskCommentType(CommentType, graphene.ObjectType):
    subtask = graphene.Field(SubTaskType)


class TaskType(DjangoObjectType):
    class Meta:
        model = Task
        fields = (
            'id',
            'name',
            'description',
            'overview',
            'implementation_notes',
            'category',
            'how_to_guide',
            'updated_at',
            'tier',
        )

    assignees = graphene.List(UserType)
    progress = graphene.Int(default_value=0)
    badges = graphene.List(graphene.String)
    program_id = graphene.String()
    tier = graphene.String()
    category = graphene.String()
    resources = graphene.List(ResourceType)
    subtasks = graphene.List(SubTaskGroupType)
    comments = graphene.List(TaskCommentType)
    customer_number = graphene.String()
    unlocked_certificates = graphene.List(graphene.String)

    def resolve_assignees(self, info):
        program_loader = info.context.loaders.program
        return program_loader.task_assignees.load(self)

    def resolve_progress(self, info):
        program_loader = info.context.loaders.program
        return program_loader.task_progress.load(self)

    def resolve_badges(self, info):
        program_loader = info.context.loaders.program
        return program_loader.task_badge.load(self)

    def resolve_program_id(self, info):
        return self.program.id

    def resolve_tier(self, info):
        d = dict(TASK_TIERS)
        return d[self.tier]

    def resolve_category(self, info):
        return self.category

    def resolve_customer_number(self, info):
        return self.customer_identifier

    def resolve_unlocked_certificates(self, info):
        program_loader = info.context.loaders.program
        return program_loader.task_certificates.load(self.id)

    def resolve_resources(self, info):
        resources = []
        for index, r in enumerate(self.how_to_guide):
            tags = r.get('tags', '')
            resources.append(
                ResourceType(
                    id=index,
                    name=r.get('name'),
                    description=r.get('description') or '',
                    link=r.get('link'),
                    resource_type=r.get('type'),
                    tags=tags.split(',') if tags else [],
                )
            )

        return resources

    def resolve_subtasks(self, info):
        groups = []
        cache_name = (
            f'unlocked_subtasks_for_task_{self.id}_organization_'
            f'{self.program.organization.id}'
        )
        unlocked_subtasks = self.get_unlocked_subtasks(cache_name=cache_name)
        user_subtasks = self.user_subtasks
        for index, g in enumerate(
            [SUBTASK_DOCUMENTATION, SUBTAKS_IMPLEMENTATION, SUBTASK_POLICY]
        ):
            unlocked_subtasks_by_group = unlocked_subtasks.filter(group=g)
            user_subtasks_by_group = user_subtasks.filter(group=g)
            subtask_list = user_subtasks_by_group
            if unlocked_subtasks_by_group:
                subtask_list = unlocked_subtasks_by_group.union(
                    user_subtasks_by_group
                ).order_by('sort_index')
            groups.append(SubTaskGroupType(id=index, name=g, subtasks=subtask_list))
        return groups

    def resolve_comments(self, info):
        comments = []
        filtered_comments = (
            self.comments.all().filter(is_deleted=False).order_by('created_at')
        )

        for c in filtered_comments:
            filtered_replies = (
                c.replies.all().filter(is_deleted=False).order_by('created_at')
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
                TaskCommentType(
                    id=c.id,
                    owner=c.owner,
                    owner_name=c.owner_name,
                    content=c.content,
                    subtask=c.task.first().subtask,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                    is_deleted=c.is_deleted,
                    state=c.state,
                    replies=replies,
                )
            )
        return comments


class TaskTierType(graphene.ObjectType):
    id = graphene.Int(required=True)
    name = graphene.String()
    tasks = graphene.List(TaskType)

    def resolve_name(self, info):
        d = dict(TASK_TIERS)
        return d[self.name]


FIRST_5_CERTIFICATES = 5


class ProgramCertificatesType(graphene.ObjectType):
    certificates = graphene.List(CertificateType)
    all_certificates = graphene.List(CertificateType)

    def resolve_certificates(self, info, **kwargs):
        certificates = self.get_all_certificates(
            cache_name=(
                f'certificates_for_program_{self.id}'
                f'_organization_{self.organization.id}'
            )
        )
        return certificates[:FIRST_5_CERTIFICATES]

    def resolve_all_certificates(self, info, **kwargs):
        certificates = self.get_all_certificates(
            cache_name=(
                'certificates_for_program_'
                f'{self.id}_organization_{self.organization.id}'
            )
        )
        return certificates


class ProgramDetailType(DjangoObjectType):
    class Meta:
        model = Program
        fields = ('id', 'name', 'program_lead', 'static_icon', 'animated_icon')

    progress = graphene.Int(default_value=0)

    def resolve_progress(self, info, **kwargs):
        return self.progress_reloaded


class ProgramType(DjangoObjectType):
    class Meta:
        model = Program
        fields = (
            'id',
            'name',
            'description',
            'sort_index',
            'program_lead',
            'static_icon',
            'animated_icon',
        )

    progress = graphene.Int(default_value=0)
    is_locked = graphene.Boolean(default_value=True)
    certifications = graphene.List(CertificateType)
    all_certifications = graphene.List(CertificateType)
    all_certificates_count = graphene.Int(default_value=0)

    def resolve_progress(self, info, **kwargs):
        return self.progress_reloaded

    def resolve_certifications(self, info, **kwargs):
        certificates = self.get_all_certificates(
            cache_name=(
                f'certificates_for_program_{self.id}_organization'
                f'_{self.organization.id}'
            )
        )
        return certificates[:FIRST_5_CERTIFICATES]

    def resolve_all_certifications(self, info, **kwargs):
        certificates = self.get_all_certificates(
            cache_name=(
                f'certificates_for_program_{self.id}_organization'
                f'_{self.organization.id}'
            )
        )
        return certificates

    def resolve_all_certificates_count(self, info):
        certificates = self.get_all_certificates(
            cache_name=(
                f'certificates_for_program_{self.id}_organization'
                f'_{self.organization.id}'
            )
        )
        return len(certificates)

    def resolve_is_locked(self, info):
        return self.is_locked


class OrganizationProgramsType(graphene.ObjectType):
    data = graphene.List(ProgramType)


class ProgramResponseType(graphene.ObjectType):
    program = graphene.Field(ProgramType)
    tasks = graphene.List(TaskTierType)


class ProgramTasksType(graphene.ObjectType):
    tasks = graphene.List(TaskTierType)


class ArchivedSubtaskType(DjangoObjectType):
    class Meta:
        model = ArchivedSubtask
        fields = ('id', 'data', 'created_at', 'updated_at')


class ArchivedUserType(DjangoObjectType):
    class Meta:
        model = ArchivedUser
        fields = ('id', 'first_name', 'last_name', 'email')


class ArchivedEvidenceReturnType(DjangoObjectType):
    class Meta:
        model = ArchivedEvidence
        fields = ('id', 'name', 'description', 'type', 'created_at', 'updated_at')

    owner = graphene.Field(ArchivedUserType)

    def resolve_owner(self, info):
        return self.owner


class ArchivedTaskType(DjangoObjectType):
    class Meta:
        model = ArchivedTask
        fields = (
            'id',
            'data',
            'created_at',
            'updated_at',
        )

    subtasks = graphene.List(ArchivedSubtaskType)
    evidence = graphene.List(ArchivedEvidenceReturnType)

    def resolve_subtasks(self, info):
        return self.subtasks.all()

    def resolve_evidence(self, info):
        return self.archived_evidence.all()


class ArchivedEvidenceOwnerType(graphene.ObjectType):
    first_name = graphene.String(required=True)
    last_name = graphene.String(required=True)
    email = graphene.String(required=True)


class ArchivedEvidenceObjectType(graphene.ObjectType):
    id = graphene.String(required=True)
    name = graphene.String(required=True)
    updated_at = graphene.DateTime()
    extension = graphene.String()
    owner = graphene.Field(ArchivedUserType)


class ArchivedEvidenceResponseType(graphene.ObjectType):
    task_id = graphene.String(required=True)
    collection = graphene.List(ArchivedEvidenceObjectType)


def map_archived_evidence(archived_evidence):
    attached_evidence = []
    for ae in archived_evidence:
        attached_evidence.append(
            ArchivedEvidenceObjectType(
                id=ae.id,
                name=ae.name,
                updated_at=ae.updated_at,
                owner=ae.owner,
                extension=get_file_extension(ae.file.name),
            )
        )
    return attached_evidence
