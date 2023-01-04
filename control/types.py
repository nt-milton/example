import graphene
from django.db.models import Count, Q
from graphene_django.types import DjangoObjectType

import evidence.constants as constants
from action_item.constants import TYPE_CONTROL
from action_item.models import ActionItem, ActionItemStatus
from blueprint.models import EvidenceMetadataBlueprint, ImplementationGuideBlueprint
from certification.models import Certification, UnlockedOrganizationCertification
from certification.types import LogoType
from comment.types import BaseCommentType, CommentType
from control.models import Control, ControlPillar
from control.utils.factory import create_tray_keys_by_reference_id
from evidence.utils import get_content_id
from laika.legacy_types import TaskLegacyType
from laika.types import FileType, PaginationResponseType
from laika.utils.html import CustomHTMLParser
from laika.utils.permissions import map_permissions
from user.types import UserType


class EvidenceType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    description = graphene.String()
    link = graphene.String()
    evidence_type = graphene.String()
    date = graphene.DateTime()
    linkable = graphene.Boolean()
    content_id = graphene.String()

    def resolve_link(self, info):
        return (
            self.file.url
            if self.file
            and self.type
            in [
                constants.FILE,
                constants.TEAM,
                constants.OFFICER,
                constants.LAIKA_PAPER,
            ]
            else ''
        )

    def resolve_evidence_type(self, info):
        return self.type

    def resolve_date(self, info):
        return self.created_at

    def resolve_linkable(self, info):
        return self.type not in (
            constants.FILE,
            constants.TEAM,
            constants.OFFICER,
            constants.LAIKA_PAPER,
        )

    def resolve_content_id(self, info):
        return get_content_id(self)


class ControlEvidenceType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    description = graphene.String()
    link = graphene.String()
    evidence_type = graphene.String()
    date = graphene.DateTime()
    linkable = graphene.Boolean()
    content_id = graphene.String()


class ControlCertificationType(graphene.ObjectType):
    id = graphene.String()
    display_name = graphene.String()
    logo = graphene.Field(LogoType)


class ControlPillarType(DjangoObjectType):
    class Meta:
        model = ControlPillar
        fields = ('id', 'name', 'description', 'illustration', 'acronym')

    id = graphene.Int()
    name = graphene.String()
    description = graphene.String()
    illustration = graphene.Field(FileType)

    def resolve_illustration(self, info):
        return self.illustration or None


class ImplementationGuideBlueprintType(DjangoObjectType):
    class Meta:
        model = ImplementationGuideBlueprint
        fields = ('description',)


class ControlCommentType(CommentType, graphene.ObjectType):
    pass


class ControlSummaryStatsType(graphene.ObjectType):
    healthy = graphene.Int()
    not_implemented = graphene.Int()
    flagged = graphene.Int()
    no_data = graphene.Int()
    no_monitors = graphene.Int()


class GroupItemType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()
    firstName = graphene.String()
    lastName = graphene.String()


class FilterGroupType(graphene.ObjectType):
    id = graphene.String()
    category = graphene.String()
    items = graphene.List(GroupItemType)


class ControlType(DjangoObjectType):
    class Meta:
        model = Control
        fields = (
            'id',
            'name',
            'reference_id',
            'status',
            'category',
            'display_id',
            'frequency',
            'description',
            'implementation_notes',
            'has_new_action_items',
            'action_items',
            'created_at',
            'updated_at',
        )

    tags = graphene.List(graphene.String)
    permissions = graphene.List(graphene.String)
    owner_details = graphene.List(UserType)
    administrator_details = graphene.Field(UserType)
    approver_details = graphene.Field(UserType)
    related_tasks = graphene.List(TaskLegacyType)
    related_policies = graphene.List(graphene.String)
    implementation_notes = graphene.String()
    category = graphene.String()
    frequency = graphene.String()
    display_id = graphene.String()
    certifications = graphene.List(graphene.String)
    evidence = graphene.List(ControlEvidenceType)
    # This is because if I try to return all certifications in certifications
    # field when getting a task related controls it will time out because there
    # are a lot of certifications per control so I'm returning a small set here
    partial_certifications = graphene.List(ControlCertificationType)
    all_certifications = graphene.List(ControlCertificationType)
    unlock_certifications = graphene.List(ControlCertificationType)
    total_certifications_count = graphene.Int()
    health = graphene.String()
    flaggedMonitors = graphene.Int()
    pillar = graphene.Field(ControlPillarType)
    implementation_guide_blueprint = graphene.Field(ImplementationGuideBlueprintType)
    previous = graphene.ID()
    next = graphene.ID()
    comments = graphene.List(ControlCommentType)
    reference_id = graphene.String()
    has_new_action_items = graphene.Boolean()
    group_id = graphene.Int()
    has_pending_required_action_items = graphene.Boolean()
    all_action_items_have_no_assignees = graphene.Boolean()

    def resolve_owner_details(self, info):
        return self.owners

    def resolve_health(self, info):
        return self.health

    def resolve_flaggedMonitors(self, info):
        return self.flaggedMonitors

    def resolve_approver_details(self, info):
        return self.approver

    def resolve_administrator_details(self, info):
        return self.administrator

    def resolve_implementation_notes(self, info):
        return self.implementation_notes

    def resolve_tags(self, info):
        return self.tags.all()

    def resolve_group_id(self, info):
        if self.group and self.group.first():
            return self.group.first().id

        return None

    def resolve_permissions(self, info):
        users = self.owners + [self.approver, self.administrator]

        return map_permissions(info.context.user, 'control', users)

    def resolve_evidence(self, info):
        all_evidence = (
            self.evidence.all()
            .exclude(type=constants.POLICY, policy__is_published=False)
            .order_by('-created_at')
        )
        evidence = []

        for e in all_evidence:
            evidence.append(
                # TODO: This should return instances of evidence and reuse the
                # EvidenceType instead of using ControlEvidenceType.
                ControlEvidenceType(
                    id=e.id,
                    name=e.name,
                    link=e.file.url
                    if e.file
                    and e.type in [constants.FILE, constants.TEAM, constants.OFFICER]
                    else '',
                    description=e.description,
                    date=e.created_at,
                    evidence_type=e.type,
                    linkable=(
                        e.type
                        not in (constants.FILE, constants.TEAM, constants.OFFICER)
                    ),
                    content_id=get_content_id(e),
                )
            )
        return evidence

    def resolve_related_policies(self, info):
        return []

    def resolve_category(self, info):
        return self.category

    def resolve_frequency(self, info):
        return self.frequency

    def resolve_display_id(self, info):
        if self.organization.roadmap.all().first():
            return self.display_id
        return f'CTRL-{self.display_id}'

    def resolve_certifications(self, info):
        sections = self.certification_sections.all()
        return set(
            [f'{section.certification.name}-{section.name}' for section in sections]
        )

    def resolve_all_certifications(self, info):
        certifications = Certification.objects.filter(
            sections__controls=self
        ).distinct()

        return [
            ControlCertificationType(
                id=certification.id,
                display_name=certification.name,
                logo=LogoType(id=certification.logo.name, url=certification.logo.url)
                if certification.logo
                else None,
            )
            for certification in certifications
        ]

    def resolve_unlock_certifications(self, info):
        certifications = Certification.objects.filter(
            sections__controls=self,
            unlocked_organizations__organization=self.organization,
        ).distinct()

        return [
            ControlCertificationType(
                id=certification.id,
                display_name=certification.name,
                logo=LogoType(id=certification.logo.name, url=certification.logo.url)
                if certification.logo
                else None,
            )
            for certification in certifications
        ]

    def resolve_partial_certifications(self, info):
        unlocked_certs = UnlockedOrganizationCertification.objects.filter(
            organization=info.context.user.organization
        ).values_list('certification__id', flat=True)

        unlocked_sections = self.certification_sections.filter(
            certification__id__in=unlocked_certs
        ).distinct('certification__id')

        locked_sections = self.certification_sections.exclude(
            certification__id__in=unlocked_certs
        ).distinct('certification__id')

        all_sections = [*unlocked_sections, *locked_sections]

        certifications = []
        for section in all_sections[:3]:
            display_name = f'{section.certification.name}-{section.name}'
            logo = section.certification.logo
            certifications.append(
                ControlCertificationType(
                    id=section.certification.id,
                    display_name=display_name,
                    logo=LogoType(id=logo.name, url=logo.url) if logo else None,
                )
            )
        return certifications

    def resolve_total_certifications_count(self, info):
        return self.certification_sections.count()

    def resolve_pillar(self, info):
        return self.pillar

    def resolve_implementation_guide_blueprint(self, info):
        return self.implementation_guide_blueprint

    def resolve_next(self, info):
        return getattr(self.next, 'id', None)

    def resolve_previous(self, info):
        return getattr(self.previous, 'id', None)

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
                ControlCommentType(
                    id=c.id,
                    owner=c.owner,
                    owner_name=c.owner_name,
                    content=c.content,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                    is_deleted=c.is_deleted,
                    state=c.state,
                    replies=replies,
                )
            )
        return comments

    def resolve_has_pending_required_action_items(self, info):
        if self.status == 'IMPLEMENTED':
            return False

        pending_action_items = self.action_items.filter(
            is_required=True,
            status__in=[ActionItemStatus.NEW, ActionItemStatus.PENDING],
        )

        return pending_action_items.exists()

    def resolve_all_action_items_have_no_assignees(self, info):
        action_items = self.action_items.filter(
            status__in=[ActionItemStatus.NEW, ActionItemStatus.PENDING]
        ).aggregate(unassigned=Count('pk', filter=Q(assignees=None)), total=Count('pk'))
        return action_items['total'] == action_items['unassigned']


class ControlsResponseType(graphene.ObjectType):
    data = graphene.List(ControlType)
    permissions = graphene.List(graphene.String)
    health_stats = graphene.Field(ControlSummaryStatsType)
    pagination = graphene.Field(PaginationResponseType)


class ControlEvidenceResponseType(graphene.ObjectType):
    data = graphene.List(EvidenceType)
    pagination = graphene.Field(PaginationResponseType)


class ControlsFiltersResponseType(graphene.ObjectType):
    data = graphene.List(FilterGroupType)


class TrayDataType(graphene.ObjectType):
    type_key = graphene.String()
    description_key = graphene.String()
    label_key = graphene.String()


class EvidenceMetadataType(graphene.ObjectType):
    id = graphene.String()
    reference_id = graphene.String()
    name = graphene.String()
    description = graphene.String()
    attachment = graphene.Field(FileType)

    def resolve_attachment(self, info):
        if not self.attachment:
            return None

        return FileType(name=self.attachment.name, url=self.attachment.url)


class ControlActionItemType(DjangoObjectType):
    class Meta:
        model = ActionItem
        fields = (
            'id',
            'name',
            'description',
            'completion_date',
            'display_id',
            'due_date',
            'is_required',
            'is_recurrent',
            'recurrent_schedule',
            'metadata',
        )

    status = graphene.String()
    recurrent_schedule = graphene.String()

    owner = graphene.Field(UserType)
    controls = graphene.List(ControlType)
    evidences = graphene.List(EvidenceType)
    tray_data = graphene.Field(TrayDataType)
    evidence_metadata = graphene.Field(EvidenceMetadataType)

    def resolve_evidence_metadata(self, info):
        if self.metadata.get('type') != TYPE_CONTROL:
            return None
        try:
            return EvidenceMetadataBlueprint.objects.get(
                reference_id=self.metadata.get('referenceId')
            )
        except EvidenceMetadataBlueprint.DoesNotExist:
            return None

    def resolve_owner(self, info):
        if self.assignees.exists():
            return self.assignees.first()

        return None

    def resolve_controls(self, info):
        if self.controls.exists():
            return self.controls.all()

    def resolve_evidences(self, info):
        if self.evidences.exists():
            return self.evidences.all()

        return None

    def resolve_description(self, info):
        if self.metadata.get('type') == TYPE_CONTROL:
            html_parser = CustomHTMLParser()
            return html_parser.add_data_attribute(
                'a',
                self.description,
                'testid',
                f'ai-{self.metadata.get("referenceId")}',
                {'Learn More': True},
            )

        return self.description

    def resolve_tray_data(self, info):
        metadata = self.metadata
        if metadata and self.metadata.get('referenceId'):
            type_key, description_key, label_key = create_tray_keys_by_reference_id(
                metadata.get('referenceId'), info.context.user.organization
            )
            if type_key and description_key and label_key:
                return TrayDataType(type_key, description_key, label_key)
        return None


class ControlsPerPillar(graphene.ObjectType):
    id = graphene.String()
    family_name = graphene.String()
    family_controls = graphene.List(ControlType)


class ControlBannerCounterResponseType(graphene.ObjectType):
    total_controls = graphene.Int()
    assigned_controls = graphene.Int()
