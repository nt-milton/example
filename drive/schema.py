import logging
import operator
from datetime import timedelta

import graphene
from django.db.models import F, Q
from django.db.models.expressions import Value
from django.db.models.fields import CharField
from django.db.models.functions.comparison import Cast

from drive.types import (
    DocumentsResponseType,
    DriveEvidenceType,
    DriveResponseIdType,
    DriveResponseType,
    FilterGroupResponseType,
    FiltersDocumentType,
    LaikaLogsResponseType,
    LaikaLogsType,
    LaikaPaperResponseType,
    map_evidence,
)
from evidence.constants import FILE, FILTER_TYPE, LAIKA_PAPER
from evidence.evidence_handler import get_file_name_without_ext
from evidence.models import Evidence, IgnoreWord
from evidence.utils import has_metadata_tag
from fieldwork.utils import get_order_info, get_pagination_info
from laika.auth import login_required, permission_required
from laika.backends.concierge_backend import ConciergeAuthenticationBackend
from laika.backends.laika_backend import AuthenticationBackend
from laika.cache import cache_func
from laika.decorators import laika_service, service
from laika.types import OrderInputType, PaginationInputType
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.exceptions import service_exception
from laika.utils.files import get_file_extension
from laika.utils.get_organization_by_user_type import get_organization_by_user_type
from laika.utils.paginator import get_paginated_result
from organization.models import Organization
from training.models import Training
from training.schema import TrainingUserTypes

from .constants import DEFAULT_PAGE_SIZE
from .helpers.filter_builder import FilterBuilder
from .helpers.filter_helpers import build_drive_order_by_clause, get_document_filters
from .models import (
    CertificatesOrderBy,
    DaysOrderBy,
    DriveEvidence,
    OwnerOrderBy,
    PlaybooksOrderBy,
    TagsOrderBy,
)
from .mutations import (
    AddDriveEvidence,
    AddLaikaPaperIgnoreWord,
    CreateLaikaPaper,
    DeleteDriveEvidence,
    UpdateDocument,
    UpdateDocumentOwner,
    UpdateLaikaPaper,
)
from .utils import evidence_and_system_tags, filter_templates_query

FIRST_PAGE = 1

logger = logging.getLogger('drive')


def create_drive_collection(evidence_by_type):
    return {
        's3_files': map_evidence(evidence_by_type.get(FILE, [])),
        'laika_papers': map_evidence(evidence_by_type.get(LAIKA_PAPER, [])),
    }


def create_filter_data(drive):
    playbooks = [
        {'name': p.name, 'id': p.name}
        for p in drive.organization.programs.all()
        if not p.is_locked
    ]
    certificates = [
        {'name': uc.certification.name, 'id': uc.certification.name}
        for uc in drive.organization.unlocked_and_archived_unlocked_certs.all()
    ]

    cache_name = f'tags_filter_{drive.organization.id}'
    cached_tags = evidence_and_system_tags(drive.evidence, cache_name=cache_name)

    tags = list(map(lambda tag: {'name': tag, 'id': tag}, cached_tags))

    has_no_evidence = drive.evidence.count() == 0
    filter_groups = [
        {
            'id': 'time',
            'name': 'By Time',
            'items': [
                {
                    'id': 'last_seven_days',
                    'name': 'Last 7 Days',
                    'sub_items': [],
                    'disabled': has_no_evidence,
                },
                {
                    'id': 'last_month',
                    'name': 'Last Month',
                    'sub_items': [],
                    'disabled': has_no_evidence,
                },
                {
                    'id': 'last_quarter',
                    'name': 'Last Quarter',
                    'sub_items': [],
                    'disabled': has_no_evidence,
                },
            ],
        },
        {
            'id': 'tags',
            'name': 'By Tags',
            'items': [
                {
                    'id': 'playbooks',
                    'name': 'Evidence From Playbooks',
                    'sub_items': playbooks,
                    'disabled': len(playbooks) == 0,
                },
                {
                    'id': 'certificates',
                    'name': 'Evidence By Certificates',
                    'sub_items': certificates,
                    'disabled': len(certificates) == 0,
                },
                {
                    'id': 'tags',
                    'name': 'Other Generated Tags',
                    'sub_items': tags,
                    'disabled': len(tags) == 0,
                },
            ],
        },
    ]
    return filter_groups


def fulltable_search(sc, drive, filtered_evidence):
    playbooks = [
        p.name
        for p in drive.organization.programs.all()
        if not p.is_locked and sc.lower() in p.name.lower()
    ]

    certificates = sorted(
        [
            uc.certification.name
            for uc in drive.organization.unlocked_and_archived_unlocked_certs.all()
            if sc.lower() in uc.certification.name.lower()
        ]
    )

    filter_query = Q()
    for value in playbooks + certificates:
        cache_name = f'evidence_for_{drive.organization.name}_{value}'
        filter_query.add(
            Q(
                evidence__in=all_evidence_with_metadata_tags(
                    filtered_evidence, value, cache_name=cache_name
                )
            ),
            Q.OR,
        )

    return filtered_evidence.filter(
        Q(evidence__name__icontains=sc)
        | Q(evidence__name__endswith=sc)
        | Q(evidence__tags__name__icontains=sc)
        | Q(
            evidence__system_tags__name__in=DriveEvidence.objects.subtasks_with_tag(
                drive.organization, sc
            )
        )
        | Q(owner__first_name__icontains=sc)
        | Q(owner__last_name__icontains=sc)
        | filter_query
    )


def filter_drive_evidence(drive, info, organization, **kwargs):
    search_criteria = kwargs.get('search_criteria')
    evidence_id = kwargs.get('evidence_id')
    filter_by = kwargs.get('filter', {})
    all_drive_evidence = drive.evidence.all()
    filter_query = get_filter_query(
        filter_by, info.context.user, all_drive_evidence, organization
    )

    if evidence_id:
        filter_query.add(Q(evidence__id=evidence_id), Q.AND)

    order_by = kwargs.get('order_by', '')
    filtered_evidence = (
        all_drive_evidence.filter(filter_query).sort(order_by).distinct()
    )

    if search_criteria:
        filtered_evidence = fulltable_search(search_criteria, drive, filtered_evidence)

    if all_drive_evidence.count() == 0:
        return all_drive_evidence

    return filtered_evidence


def create_documents_collection(evidence_by_type):
    s3_files = evidence_by_type.get(FILE, [])
    laika_papers = evidence_by_type.get(LAIKA_PAPER, [])
    documents = s3_files + laika_papers
    return map_evidence(documents)


@cache_func
def all_evidence_with_metadata_tags(drive_evidence, tag_value, **kwargs):
    evidence_with_metadata_tags = []
    for de in drive_evidence:
        if has_metadata_tag(de.evidence, tag_value):
            evidence_with_metadata_tags.append(de.evidence)

    return evidence_with_metadata_tags


def _if_filter_by_owner(filter_query, field, value):
    if field == OwnerOrderBy.FIELD.value:
        return filter_query.add(
            Q(owner__first_name__icontains=value)
            | Q(owner__last_name__icontains=value),
            Q.AND,
        )
    return filter_query.add(Q(), Q.AND)


def _if_filter_by_tag(organization, filter_query, field, value):
    if field == TagsOrderBy.FIELD.value:
        return filter_query.add(
            Q(evidence__tags__name__icontains=value)
            | Q(
                evidence__system_tags__name__in=DriveEvidence.objects.subtasks_with_tag(
                    organization, value
                )
            ),
            Q.AND,
        )
    return filter_query.add(Q(), Q.AND)


def _if_filter_by_days(organization, filter_query, field, value):
    time_filter = None
    if value:
        time_filter = next(
            (
                filter[1]
                for filter in DaysOrderBy.FILTERS.value
                if filter[0] == value.upper()
            ),
            None,
        )

    if field == DaysOrderBy.FIELD.value and time_filter:
        de = organization.drive.last_updated_evidence
        d = de.evidence.updated_at - timedelta(days=time_filter)
        return filter_query.add(Q(evidence__updated_at__gte=d), Q.AND)
    return filter_query.add(Q(), Q.AND)


def _if_filter_by_playbooks_or_certificates(
    organization, drive_evidence, filter_query, field, value
):
    if field in [CertificatesOrderBy.FIELD.value, PlaybooksOrderBy.FIELD.value]:
        cache_name = f'evidence_for_{organization.name}_{value}'
        return filter_query.add(
            Q(
                evidence__in=all_evidence_with_metadata_tags(
                    drive_evidence, value, cache_name=cache_name
                )
            ),
            Q.AND,
        )
    return filter_query.add(Q(), Q.AND)


def _if_filter_by_document_type(filter_query, field, value):
    if field == FILTER_TYPE:
        return filter_query.add(Q(evidence__name__endswith=value), Q.AND)
    return filter_query.add(Q(), Q.AND)


def is_other_filter(field):
    return field not in [
        OwnerOrderBy.FIELD.value,
        TagsOrderBy.FIELD.value,
        DaysOrderBy.FIELD.value,
        CertificatesOrderBy.FIELD.value,
        PlaybooksOrderBy.FIELD.value,
        FILTER_TYPE,
    ]


def get_filter_query(filter_by, user, drive_evidence, organization):
    if organization is None:
        organization = user.organization

    filter_query = Q(**filter_templates_query(user))

    for field, value in filter_by.items():
        _if_filter_by_owner(filter_query, field, value)
        _if_filter_by_tag(organization, filter_query, field, value)
        _if_filter_by_days(organization, filter_query, field, value)
        _if_filter_by_playbooks_or_certificates(
            organization, drive_evidence, filter_query, field, value
        )
        _if_filter_by_document_type(filter_query, field, value)
        if is_other_filter(field):
            filter_query.add(Q(**{f'evidence__{field}__icontains': value}), Q.AND)

    return filter_query


class Mutation(graphene.ObjectType):
    update_document = UpdateDocument.Field()
    add_drive_evidence = AddDriveEvidence.Field()
    add_laika_paper_ignore_word = AddLaikaPaperIgnoreWord.Field()
    delete_drive_evidence = DeleteDriveEvidence.Field()
    create_laika_paper = CreateLaikaPaper.Field()
    update_laika_paper = UpdateLaikaPaper.Field()
    update_document_owner = UpdateDocumentOwner.Field()


class DriverFilterItemType(graphene.ObjectType):
    id = graphene.String()
    name = graphene.String()


class FilterItemsGroupType(graphene.ObjectType):
    id = graphene.String()
    category = graphene.String()
    items = graphene.List(DriverFilterItemType)


class DocumentsFiltersResponseType(graphene.ObjectType):
    data = graphene.List(FilterItemsGroupType)


class Query(object):
    drive = graphene.Field(
        DriveResponseType,
        organization_id=graphene.UUID(),
        search_criteria=graphene.String(),
        evidence_id=graphene.String(),
        order_by=graphene.Argument(OrderInputType, required=False),
        filter=graphene.JSONString(required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
    )
    filtered_drives = graphene.Field(
        DriveResponseType,
        organization_id=graphene.UUID(),
        order_by=graphene.Argument(OrderInputType, required=False),
        filters=graphene.Argument(FiltersDocumentType, required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
    )
    drive_evidence = graphene.Field(DocumentsResponseType)
    all_drive_evidence = graphene.Field(
        DriveResponseIdType,
        search_criteria=graphene.String(),
        filter=graphene.JSONString(required=False),
        organization_id=graphene.String(),
    )
    laika_paper = graphene.Field(
        LaikaPaperResponseType,
        laika_paper_id=graphene.Int(required=True),
        organization_id=graphene.UUID(),
    )
    laika_papers = graphene.List(
        DriveEvidenceType,
        only_templates=graphene.Boolean(),
        organization_id=graphene.UUID(),
    )
    filter_groups = graphene.Field(
        FilterGroupResponseType, organization_id=graphene.UUID()
    )
    laika_logs = graphene.Field(
        LaikaLogsResponseType,
        search_criteria=graphene.String(required=False),
        order_by=graphene.Argument(OrderInputType, required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
    )
    drive_filters = graphene.Field(DocumentsFiltersResponseType)

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'drive.view_driveevidence',
            },
        ],
        exception_msg='Failed to retrieve drive evidence list',
    )
    def resolve_drive(self, info, **kwargs):
        organization_id = kwargs.get('organization_id')
        pagination = kwargs.get('pagination')
        page_size = pagination.get('page_size', DEFAULT_PAGE_SIZE)
        page = pagination.get('page')
        organization = info.context.user.organization

        if organization_id:
            organization = Organization.objects.get(id=organization_id)

        drive = organization.drive
        all_drive_evidence = filter_drive_evidence(drive, info, organization, **kwargs)

        paginated_result = get_paginated_result(all_drive_evidence, page_size, page)
        drive_evidence_data = paginated_result.get('data')

        evidence_collection = map_evidence(drive_evidence_data)
        return DriveResponseType(
            id=drive.id,
            organization_name=organization.name,
            collection=evidence_collection,
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @login_required
    @service_exception('Cannot get documents evidence')
    @permission_required('drive.view_driveevidence')
    def resolve_drive_evidence(self, info, **kwargs):
        drive = info.context.user.organization.drive
        all_drive_evidence = (
            drive.evidence.all()
            .filter(is_template=False)
            .order_by('evidence__created_at')
        )

        evidence_collection = map_evidence(all_drive_evidence)
        return DocumentsResponseType(id=drive.id, documents=evidence_collection)

    @laika_service(
        permission='drive.view_driveevidence',
        exception_msg='Failed to get laika logs',
    )
    def resolve_laika_logs(self, info, **kwargs):
        search_criteria = kwargs.get('search_criteria', '')
        current_user_role = info.context.user.role
        if (
            current_user_role == TrainingUserTypes.SuperAdmin.value
            or current_user_role == TrainingUserTypes.OrganizationAdmin.value
        ):
            trainings = Training.objects.filter(
                organization=info.context.user.organization
            )
        else:
            trainings = Training.objects.filter(
                organization=info.context.user.organization
            ).filter(Q(roles__contains=current_user_role))

        trainings = (
            trainings.filter(name__icontains=search_criteria)
            .annotate(source=Value('Trainings', output_field=CharField()))
            .values('name', 'source')
            .annotate(id=Cast(F('id'), output_field=CharField()))
        )
        teams = (
            info.context.user.organization.teams.filter(name__icontains=search_criteria)
            .annotate(source=Value('Teams', output_field=CharField()))
            .values('name', 'source')
            .annotate(id=Cast(F('id'), output_field=CharField()))
        )
        officers = info.context.user.organization.officers
        organization_vendors = info.context.user.organization.organization_vendors

        laika_logs = trainings.union(teams)

        laika_logs = [
            LaikaLogsType(
                id=laika_log['id'], name=laika_log['name'], source=laika_log['source']
            )
            for laika_log in laika_logs
        ]

        if organization_vendors.count():
            laika_logs.append(
                LaikaLogsType(id='Vendors', name='Vendors', source='Vendors')
            )

        if officers.count():
            laika_logs.append(
                LaikaLogsType(id='Officers', name='Officers', source='Officers')
            )

        if kwargs.get('order_by'):
            (_, field, _, order, search_criteria) = get_order_info(kwargs)
            reverse = order == 'descend'
            laika_logs = sorted(
                laika_logs, key=operator.attrgetter(field), reverse=reverse
            )

        if search_criteria:
            laika_logs = list(
                filter(
                    lambda l_l: search_criteria.lower() in l_l.name.lower(), laika_logs
                )
            )

        pagination, page, page_size = get_pagination_info(kwargs)
        if not pagination:
            return LaikaLogsResponseType(laika_logs=laika_logs)

        paginated_result = get_paginated_result(laika_logs, page_size, page)

        return LaikaLogsResponseType(
            laika_logs=paginated_result.get('data'),
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'drive.view_driveevidence',
            },
        ],
        exception_msg='Failed to retrieve documents. Please try again',
    )
    def resolve_all_drive_evidence(self, info, **kwargs):
        organization_id = kwargs.get('organization_id')
        organization = get_organization_by_user_type(info.context.user, organization_id)
        drive = organization.drive
        all_drive_evidence_ids = filter_drive_evidence(
            drive, info, None, **kwargs
        ).values_list('evidence_id', flat=True)

        return DriveResponseIdType(ids=all_drive_evidence_ids)

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'drive.view_driveevidence',
            },
        ],
        exception_msg='Cannot get laika paper',
    )
    def resolve_laika_paper(self, info, **kwargs):
        laika_paper_id = kwargs.get('laika_paper_id')
        organization_id = kwargs.get('organization_id')
        organization = get_organization_by_user_type(info.context.user, organization_id)
        evidence = Evidence.objects.get(
            organization=organization, id=laika_paper_id, type=LAIKA_PAPER
        )
        ignore_words = IgnoreWord.objects.filter(language__evidence=evidence)
        drive_evidence = organization.drive.evidence.get(evidence=evidence)
        paper_content = evidence.file.read().decode('UTF-8')

        return LaikaPaperResponseType(
            id=evidence.id,
            laika_paper_name=evidence.name,
            laika_paper_content=paper_content,
            laika_paper_ignore_words=ignore_words,
            owner=drive_evidence.owner,
            type=LAIKA_PAPER,
        )

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'drive.view_driveevidence',
            },
        ],
        exception_msg='Cannot get laika papers',
    )
    def resolve_laika_papers(self, info, **kwargs):
        only_templates = kwargs.get('only_templates')
        drive_filter = {'drive__is_template': only_templates} if only_templates else {}

        organization = get_organization_by_user_type(
            info.context.user, kwargs.get('organization_id')
        )

        laika_papers = Evidence.objects.filter(
            organization=organization, type=LAIKA_PAPER, **drive_filter
        ).order_by('created_at')

        all_laika_papers = []

        for laika_paper in laika_papers:
            all_laika_papers.append(
                {
                    'id': laika_paper.id,
                    'name': get_file_name_without_ext(laika_paper.name),
                    'evidence_type': laika_paper.type,
                    'description': laika_paper.description,
                    'created_at': laika_paper.created_at,
                    'updated_at': laika_paper.updated_at,
                    'extension': get_file_extension(laika_paper.file.name),
                }
            )

        return all_laika_papers

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'drive.view_driveevidence',
            },
        ],
        exception_msg='Failed to retrieve filter groups list',
    )
    def resolve_filter_groups(self, info, **kwargs):
        organization_id = kwargs.get('organization_id')
        organization = info.context.user.organization

        if organization_id:
            organization = Organization.objects.get(id=organization_id)

        return FilterGroupResponseType(data=create_filter_data(organization.drive))

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'drive.view_driveevidence',
            },
        ],
        exception_msg='Failed to retrieve filter groups list',
    )
    def resolve_drive_filters(self, info, **kwargs):
        organization = info.context.user.organization
        builder = FilterBuilder(organization)
        builder.add_types()
        builder.add_owners()
        builder.add_tags()

        filters_list = builder.filter.export()
        return DocumentsFiltersResponseType(data=filters_list)

    @service(
        allowed_backends=[
            {
                'backend': ConciergeAuthenticationBackend.BACKEND,
                'permission': 'user.view_concierge',
            },
            {
                'backend': AuthenticationBackend.BACKEND,
                'permission': 'drive.view_driveevidence',
            },
        ],
        exception_msg='Failed to retrieve drive evidence list',
    )
    def resolve_filtered_drives(self, info, **kwargs):
        order_query = build_drive_order_by_clause(**kwargs)
        organization_id = kwargs.get('organization_id')
        filters = kwargs.get('filters', {})
        search = filters.get('search', '')
        search_filter = Q(evidence__name__icontains=search)
        document_filters = get_document_filters(filters)
        pagination = kwargs.get('pagination', {})
        page_size = pagination.get('page_size', DEFAULT_PAGE_SIZE)
        page = pagination.get('page', FIRST_PAGE)

        data = (
            info.context.user.organization.drive.evidence.filter(
                search_filter & document_filters
            )
            .order_by(order_query)
            .distinct()
        )

        organization = info.context.user.organization

        if organization_id:
            organization = Organization.objects.get(id=organization_id)

        drive = organization.drive

        paginated_result = get_paginated_result(data, page_size, page)
        drive_evidence_data = paginated_result.get('data')

        evidence_collection = map_evidence(drive_evidence_data)
        return DriveResponseType(
            id=drive.id,
            organization_name=organization.name,
            collection=evidence_collection,
            pagination=exclude_dict_keys(paginated_result, ['data']),
        )
