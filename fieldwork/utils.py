import io
import logging
from datetime import datetime
from typing import List

from django.core.files import File
from django.db.models import Count, F, Func, Min, Model, Q, Value
from django.db.models.fields import CharField, IntegerField
from django.db.models.functions import Cast

from audit.constants import AUDITOR_ROLES
from audit.models import Audit
from drive.models import DriveEvidence
from drive.types import DriveEvidenceType, TagsInfo, get_tags_associated_to_evidence
from evidence.constants import LAIKA_PAPER
from evidence.evidence_handler import (
    create_team_pdf_evidence,
    get_document_evidence_name,
    get_files_to_upload,
)
from fieldwork.util.evidence_request import (
    attach_officers,
    calculate_er_times_move_back_to_open,
    file_attachment_match_name,
    store_er_attachments_metrics,
    update_attachments_status,
)
from laika.constants import ATTRIBUTES_TYPE, CATEGORIES, WORD_DOCUMENT_EXTENSION
from laika.utils.dates import now_date
from laika.utils.dictionaries import exclude_dict_keys
from laika.utils.exceptions import ServiceException
from laika.utils.files import get_file_extension
from laika.utils.paginator import get_paginated_result
from laika.utils.pdf import convert_file_to_pdf
from laika.utils.query_builder import get_incredible_filter_query
from laika.utils.strings import right_replace_char_from_string
from link.models import Link
from organization.models import Organization
from policy.models import Policy
from policy.views import get_published_policy_pdf
from population.models import Sample
from training.models import Training
from training.views import get_training_pdf
from user.constants import AUDITOR, AUDITOR_ADMIN, ROLE_ADMIN, ROLE_SUPER_ADMIN
from user.helpers import get_admin_users_in_laika
from user.models import ROLES, Auditor, Team, User
from user.types import UserType
from vendor.models import Vendor
from vendor.views import get_vendors_pdf

from .constants import (
    ALL_POOL,
    ALLOW_ROLES_TO_ASSIGN_USER,
    CRITERIAS_TYPE,
    DEFAULT_PAGE,
    DEFAULT_PAGE_SIZE,
    DOCUMENT_FETCH_TYPE,
    ER_STATUS_DICT,
    EVIDENCE_ATTRIBUTES,
    LAIKA_POOL,
    LCL_CX_POOL,
    LCL_POOL,
    LO_FILE_TYPES,
    MONITOR_FILE_NAMES,
    OTHER_SOURCE_TYPE,
    POLICY_FETCH_TYPE,
    TEAM_FETCH_TYPE,
    TRAINING_FETCH_TYPE,
    VENDOR_FETCH_TYPE,
    VENDORS_NAME_FOR_AUDIT_REPORT,
)
from .models import (
    Attachment,
    CriteriaRequirement,
    Evidence,
    EvidenceMetric,
    EvidenceRequestAttachment,
    EvidenceStatusTransition,
    TemporalAttachment,
)
from .util.evidence_attachment import (
    add_laika_objects_attachments,
    add_monitors_attachments,
)

logger = logging.getLogger('fieldwork_utils')


def get_display_id_order_annotation(preffix: str, field: str = 'display_id') -> Cast:
    return Cast(
        Func(F(field), Value(preffix), Value(''), function='regexp_replace'),
        IntegerField(),
    )


def get_order_annotation_char_cast(prefix: str, field: str = 'display_id') -> Cast:
    return Cast(
        Func(F(field), Value(prefix), Value(''), function='regexp_replace'), CharField()
    )


def get_evidence_by_audit(kwargs, evidence):
    from .types import FieldworkEvidenceResponseType

    pagination, page, page_size = get_pagination_info(kwargs)

    if not pagination:
        return FieldworkEvidenceResponseType(evidence=evidence)

    paginated_result = get_paginated_result(evidence, page_size, page)

    return FieldworkEvidenceResponseType(
        evidence=paginated_result.get('data'),
        pagination=exclude_dict_keys(paginated_result, ['data']),
    )


def get_pagination_info(kwargs):
    pagination = kwargs.get('pagination')
    page = pagination.page if pagination else DEFAULT_PAGE
    page_size = pagination.page_size if pagination else DEFAULT_PAGE_SIZE

    return (pagination, page, page_size)


def update_evidence_status(
    evidence, status, transitioned_by, transition_reasons='', extra_notes=None
):
    user_role = transitioned_by.role
    is_laika_reviewed = (
        status == ER_STATUS_DICT['Submitted'] and user_role == ROLE_SUPER_ADMIN
    )

    new_evidence = []
    for er in evidence:
        current_laika_review_value = er.is_laika_reviewed
        from_status = er.status
        er.status = status
        er.is_laika_reviewed = is_laika_reviewed

        if status.lower() == ER_STATUS_DICT['Open']:
            er.times_moved_back_to_open = calculate_er_times_move_back_to_open(er)

        new_evidence.append(er)

        if status.lower() == ER_STATUS_DICT['Submitted'] and len(er.attachments) <= 0:
            raise ServiceException(
                f'Evidence selected: {er.display_id} must have at least one attachment'
            )

        update_attachments_status(status, er.attachments)

        EvidenceStatusTransition.objects.create(
            evidence=er,
            from_status=from_status,
            to_status=status,
            transition_reasons=transition_reasons,
            extra_notes=extra_notes,
            laika_reviewed=current_laika_review_value,
            transitioned_by=transitioned_by,
        )

    return new_evidence


def get_evidence_readonly(evidence, time_zone):
    copy_file = File(file=evidence.file, name=evidence.name)
    if evidence.type == LAIKA_PAPER:
        laika_paper_name = get_document_evidence_name(
            copy_file.name, evidence.type, time_zone
        )
        copy_file.file = convert_file_to_pdf(copy_file)
        copy_file.name = f'{laika_paper_name}.pdf'
    return copy_file


def create_vendors_pdf_evidence(organization, vendors_ids, time_zone):
    try:
        if not vendors_ids:
            return None, None

        vendors = organization.organization_vendors.all()
        pdf = get_vendors_pdf(organization, vendors, time_zone)
        date = now_date(time_zone, '%Y_%m_%d_%H_%M')
        file_name = f'Vendors {date}.pdf'

        if not pdf:
            logger.error(
                'Error to generate pdf with vendors '
                'for organization id '
                f'{organization.id}'
            )
            return None, None

        vendor_pdf = File(name=file_name, file=io.BytesIO(pdf))
        return vendor_pdf, file_name

    except Vendor.DoesNotExist:
        logger.warning(
            f'Organization vendors with organization_id {organization.id} '
            'does not exist'
        )
        return None, None


def create_training_pdf_evidence(organization, training_id, time_zone):
    try:
        training = Training.objects.get(organization=organization, id=training_id)
        pdf = get_training_pdf(training, time_zone)
        date = now_date(time_zone, '%Y_%m_%d_%H_%M')
        file_name = f'{training.name}_{date}.pdf'

        if pdf:
            training_pdf = File(name=file_name, file=io.BytesIO(pdf))
            return training_pdf, file_name, training

    except Training.DoesNotExist:
        logger.warning(
            f'Training with id {training.id} '
            f'and organization_id {organization.id} '
            'does not exist'
        )
        return None


def add_evidence_attachment(
    fieldwork_evidence,
    policies,
    uploaded_files,
    documents,
    officers,
    teams,
    objects_ids,
    monitors,
    vendors,
    trainings,
    time_zone,
    organization=None,
    sample_id=None,
):
    ids = []
    current_metrics, _ = EvidenceMetric.objects.get_or_create(
        evidence_request=fieldwork_evidence,
        defaults={'integrations_counter': {'general': 0}},
    )

    file_monitors_count = 0
    file_integrations_count = 0
    for file in uploaded_files:
        attachment = fieldwork_evidence.add_attachment(
            file_name=file.name, file=file, attach_type=OTHER_SOURCE_TYPE
        )
        ids.append(attachment.id)

        if file_attachment_match_name(file.name, MONITOR_FILE_NAMES):
            file_monitors_count += 1

        if file_attachment_match_name(file.name, LO_FILE_TYPES):
            file_integrations_count += 1

    if sample_id:
        sample = Sample.objects.filter(id=sample_id).first()
        if sample:
            Attachment.objects.filter(id__in=ids).update(sample=sample)

    for document in documents:
        drive_evidence = DriveEvidence.objects.get(evidence_id=document)
        evidence = drive_evidence.evidence
        evidence_readonly = get_evidence_readonly(evidence, time_zone)
        attachment = fieldwork_evidence.add_attachment(
            file_name=evidence_readonly.name,
            file=evidence_readonly,
            attach_type=DOCUMENT_FETCH_TYPE,
            origin_source_object=drive_evidence.evidence,
        )
        ids.append(attachment.id)
    for policy in policies:
        policy_obj = Policy.objects.get(pk=policy)
        new_file_name = f'{policy_obj.name}.pdf'
        attachment = fieldwork_evidence.add_attachment(
            file_name=new_file_name,
            policy=policy_obj,
            attach_type=POLICY_FETCH_TYPE,
            origin_source_object=policy_obj,
        )
        ids.append(attachment.id)

    ids = attach_officers(officers, fieldwork_evidence, organization, time_zone, ids)

    for team_id in teams:
        team = Team.objects.get(organization_id=organization.id, id=team_id)
        team_pdf, file_name = create_team_pdf_evidence(team=team, time_zone=time_zone)
        attachment = fieldwork_evidence.add_attachment(
            file_name=file_name,
            file=team_pdf,
            attach_type=TEAM_FETCH_TYPE,
            origin_source_object=team,
        )
        ids.append(attachment.id)

    (
        objects_attachments_ids,
        integrations_category_counter,
        file_integrations_count,
    ) = add_laika_objects_attachments(
        fieldwork_evidence,
        objects_ids,
        organization,
        time_zone,
        file_integrations_count,
    )
    ids += objects_attachments_ids

    monitors_ids = [monitor.id for monitor in monitors]
    monitors_attachments_ids, monitors_count = add_monitors_attachments(
        fieldwork_evidence, monitors_ids, organization, time_zone
    )
    ids += monitors_attachments_ids

    store_er_attachments_metrics(
        current_metrics,
        monitors_count,
        file_monitors_count,
        file_integrations_count,
        integrations_category_counter,
    )

    if vendors:
        vendor_pdf, file_name = create_vendors_pdf_evidence(
            organization=organization, vendors_ids=vendors, time_zone=time_zone
        )
        attachment = fieldwork_evidence.add_attachment(
            file_name=file_name, file=vendor_pdf, attach_type=VENDOR_FETCH_TYPE
        )
        ids.append(attachment.id)
    for training_id in trainings:
        training_pdf, file_name, training = create_training_pdf_evidence(
            organization=organization, training_id=training_id, time_zone=time_zone
        )
        attachment = fieldwork_evidence.add_attachment(
            file_name=file_name,
            file=training_pdf,
            attach_type=TRAINING_FETCH_TYPE,
            origin_source_object=training,
        )
        ids.append(attachment.id)
    return ids


def bulk_assign_audit_evidence(evidence, assignee):
    new_evidence = []
    for ev in evidence:
        ev.assignee = assignee
        new_evidence.append(ev)

    return new_evidence


def bulk_laika_review_evidence(evidence, review_all=False, back_to_open=False):
    new_evidence = []
    for ev in evidence:
        if review_all:
            ev.is_laika_reviewed = True
        elif back_to_open:
            ev.is_laika_reviewed = False
        else:
            ev.is_laika_reviewed = not ev.is_laika_reviewed
        ev.updated_at = datetime.now()
        new_evidence.append(ev)

    return new_evidence


EVIDENCE_ATTACHMENT_FIELD = 'attachments_num'


def format_value(value, attr_type):
    if attr_type == ATTRIBUTES_TYPE['USER']:
        return value.split(',')

    if value == 'true':
        val = True
    elif value == 'false':
        val = False
    else:
        val = value

    return val


def build_evidence_incredible_filter(filters):
    filter_query = Q()

    for filter in filters:
        if filter['field'] in EVIDENCE_ATTRIBUTES:
            attr = EVIDENCE_ATTRIBUTES[filter['field']]
            incredible_filter = get_incredible_filter_query(
                field=attr['query_path'],
                value=format_value(filter['value'], attr['attribute_type']),
                operator=filter['operator'],
                attribute_type=attr['attribute_type'],
            )

            filter_query.add(incredible_filter, Q.AND)

    return filter_query


def attachment_query_exist(filters):
    attachment_filter = [
        filter for filter in filters if filter['field'] == EVIDENCE_ATTACHMENT_FIELD
    ]
    return True if len(attachment_filter) > 0 else False


def get_fieldwork_state_filtered(filters, state_qs, audit_id):
    if attachment_query_exist(filters):
        state_qs = state_qs.annotate(
            attachments_num=Count(
                'attachment', filter=Q(attachment__is_deleted=False, audit_id=audit_id)
            )
        )

    filter_query = build_evidence_incredible_filter(filters)

    return state_qs.filter(filter_query)


def create_policies_tmp_attachments(audit, policies):
    for policy in policies:
        published_policy_file = get_published_policy_pdf(policy.id)
        if published_policy_file:
            TemporalAttachment.objects.create(
                name=f'{policy.name}.pdf',
                file=File(name=policy.name, file=published_policy_file),
                policy=policy,
                audit=audit,
            )


def create_tmp_attachment(audit, fetch_logic, file_name, file):
    TemporalAttachment.objects.create(
        name=file_name,
        file=File(name=file_name, file=io.BytesIO(file)),
        fetch_logic=fetch_logic,
        audit=audit,
    )


def delete_audit_tmp_attachments(audit):
    TemporalAttachment.objects.filter(audit=audit).delete()


def add_attachment(organization=None, fieldwork_evidence=None, input=None):
    uploaded_files = get_files_to_upload(input.get('uploaded_files', []))
    policies = input.get('policies', [])
    documents = input.get('documents', [])
    officers = input.get('officers', [])
    teams = input.get('teams', [])
    objects_ids = input.get('objects_ids', [])
    monitors = input.get('monitors', [])
    vendors = input.get('vendors', [])
    trainings = input.get('trainings', [])
    sample_id = input.get('sample_id', '')

    ids = add_evidence_attachment(
        fieldwork_evidence,
        policies,
        uploaded_files,
        documents,
        officers,
        teams,
        objects_ids,
        monitors,
        vendors,
        trainings,
        time_zone=input.time_zone,
        organization=organization,
        sample_id=sample_id,
    )
    return ids


def validate_requirement_status_change(old_status, new_status):
    invalid_updates = [
        ('open', 'completed'),
    ]
    current_change = (old_status, new_status.lower())
    if current_change in invalid_updates:
        raise ServiceException(
            f'Invalid requirement status update: {old_status} to {new_status}'
        )


def get_order_info(kwargs):
    order_by = kwargs.get('order_by', {'field': 'display_id', 'order': 'ascend'})
    field = order_by.get('field')
    order = order_by.get('order')
    filter = kwargs.get('filter', [])
    order_annotate = {}

    search_criteria = kwargs.get('search_criteria')

    return (filter, field, order_annotate, order, search_criteria)


def get_order_query(field, order):
    order_query = (
        F(field).desc(nulls_last=True)
        if order == 'descend'
        else F(field).asc(nulls_last=True)
    )
    return order_query


def get_evidence_by_args(kwargs):
    (filter, field, order_annotate, order, search_criteria) = get_order_info(kwargs)

    audit_id = kwargs.get('audit_id')
    evidence_qs = get_fieldwork_state_filtered(
        filters=filter, state_qs=Evidence.objects.all(), audit_id=audit_id
    )

    if field == 'display_id':
        order_annotate = {
            'display_id_sort': get_display_id_order_annotation(preffix='ER-')
        }
        field = 'display_id_sort'

    order_query = get_order_query(field, order)

    if search_criteria:
        evidence_qs = evidence_qs.filter(
            Q(display_id__icontains=search_criteria)
            | Q(name__icontains=search_criteria)
        )

    status = kwargs.get('status')

    if status:
        return (
            evidence_qs.filter(
                status__iexact=status, audit__id=audit_id, is_deleted=False
            )
            .annotate(attachments_num=Count('attachment'))
            .annotate(**order_annotate)
            .order_by(order_query)
        )

    return (
        evidence_qs.filter(audit__id=audit_id, is_deleted=False)
        .annotate(attachments_num=Count('attachment'))
        .annotate(**order_annotate)
        .order_by(order_query)
    )


def assign_evidence_user(req_input, organization=None):
    assignee = User.objects.get(email=req_input.get('email'))

    if assignee.role not in ALLOW_ROLES_TO_ASSIGN_USER:
        raise ServiceException(
            f'Only roles {ALLOW_ROLES_TO_ASSIGN_USER}can assign a user to evidence'
        )

    ev_org_filter_props = {'audit__organization': organization} if organization else {}

    evidence = Evidence.objects.filter(
        id__in=req_input.get('evidence_ids'),
        audit_id=req_input.get('audit_id'),
        **ev_org_filter_props,
    )

    updated_evidence = bulk_assign_audit_evidence(evidence=evidence, assignee=assignee)
    Evidence.objects.bulk_update(updated_evidence, ['assignee'])
    ids = [evidence_obj.id for evidence_obj in evidence]
    return ids


def get_audit_users_by_role(audit_id: str, role: str) -> List[UserType]:
    roles = dict(ROLES)
    audit = Audit.objects.get(id=audit_id)
    users = User.objects.filter(organization=audit.organization, role=roles[role])

    return [
        UserType(
            id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
        )
        for user in users
    ]


def get_assignees_for_evidence(kwargs):
    roles = dict(ROLES)
    allow_roles_to_assign_user = [roles['SuperAdmin'], roles['OrganizationAdmin']]
    audit = Audit.objects.get(id=kwargs.get('audit_id'))
    users = User.objects.filter(
        organization=audit.organization, role__in=allow_roles_to_assign_user
    )

    return [
        UserType(
            id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
        )
        for user in users
    ]


def get_audit_team_and_auditor_admins(audit_id: str) -> list[Auditor]:
    audit = Audit.objects.get(id=audit_id)
    audit_firms = [audit.audit_firm]
    query_filter = (
        Q(user__role__iexact=AUDITOR_ADMIN) & Q(audit_firms__in=audit_firms)
    ) | Q(audit_team__audit__id=audit_id)
    return list(Auditor.objects.filter(query_filter).distinct())


def get_audit_team_and_auditor_admins_mapped_to_usertype(
    audit_id: str,
) -> list[UserType]:
    audit_users = get_audit_team_and_auditor_admins(audit_id)

    return [
        UserType(
            id=auditor.user.id,
            username=auditor.user.username,
            first_name=auditor.user.first_name,
            last_name=auditor.user.last_name,
            email=auditor.user.email,
        )
        for auditor in audit_users
    ]


categories_value = [v.lower().strip() for c, v in CATEGORIES]


def get_category_tags(tags):
    return [t.name for t in tags if str(t.name).lower().strip() in categories_value]


def has_audit_type(tags, audit_type):
    return any(
        [t for t in tags if str(t.name).lower().strip() == audit_type.lower().strip()]
    )


def get_tags_and_categories_info(documents, audit_type):
    all_tags = []
    tags_per_doc = []
    for d in documents:
        tags = get_tags_associated_to_evidence(d.evidence)
        all_tags.extend(tags)
        tags_per_doc.append({'id': d.evidence.id, 'tags': tags})

    unique_tags = list(set(all_tags))
    return {
        'have_audit_type': has_audit_type(unique_tags, audit_type),
        'categories': list(set(get_category_tags(unique_tags))),
        'tags_per_doc': tags_per_doc,
    }


def build_criteria_data_for_report(
    criteria_requirement: list, audit_id: str
) -> list[dict]:
    criteria = []
    for criteria_req in criteria_requirement:
        requirements = []

        for requirement in (
            criteria_req.criteria.requirements.filter(
                audit_id=audit_id, is_deleted=False, exclude_in_report=False
            )
            .annotate(
                display_id_sort=get_display_id_order_annotation(
                    preffix='LCL-', field='display_id'
                )
            )
            .order_by('display_id_sort')
        ):
            requirements.append(
                {
                    'display_id': requirement.display_id,
                    'description': requirement.description,
                }
            )

        criteria.append(
            {
                'display_id': criteria_req.criteria.display_id,
                'description': criteria_req.criteria.description,
                'requirements': requirements,
            }
        )

    return criteria


def get_sso_cloud_provider(organization: Organization) -> str:
    vendors_qs = organization.vendors.filter(name__in=VENDORS_NAME_FOR_AUDIT_REPORT)
    vendors_name = [vendor.name for vendor in vendors_qs]

    sso_cloud_provider = 'sso_cloud_provider'

    if len(vendors_name) == 1:
        sso_cloud_provider = ''.join(vendors_name)
    elif len(vendors_name) > 1:
        sso_cloud_provider = right_replace_char_from_string(
            ', '.join(vendors_name), ', ', ' and ', 1
        )

    return sso_cloud_provider


def get_sso_cloud_providers_quantity(organization: Organization) -> int:
    return organization.vendors.filter(name__in=VENDORS_NAME_FOR_AUDIT_REPORT).count()


def get_trust_service_categories(tsc: list) -> str:
    return right_replace_char_from_string(', '.join(tsc), ', ', ' and ', 1)


def save_content_audit_draft_report_file(
    audit: Audit, organization: Organization, content: str
) -> File:
    new_file = File(
        name=f'{organization.name}_{audit.name}_report.html',
        file=io.BytesIO(content.encode()),
    )

    audit_status = audit.status.first()
    audit_status.draft_report_file_generated = new_file
    audit_status.save()

    return new_file


def get_draft_report_mentions_users(audit: Audit) -> list[UserType]:
    admin_users = get_admin_users_in_laika(audit.organization.id)
    audit_team = Auditor.objects.filter(audit_team__audit=audit).distinct()

    auditors = [a.user for a in audit_team]
    users = [user for user in admin_users]

    users.extend(auditors)
    return [
        UserType(
            id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            role=user.role,
        )
        for user in users
    ]


def map_policies_to_evidence_req_attachment(
    policies: list[Policy],
) -> list[EvidenceRequestAttachment]:
    policies_mapped = []
    for policy in policies:
        policies_mapped.append(
            EvidenceRequestAttachment(
                id=policy.id,
                name=f'{policy.name}.policy',
                created_at=policy.created_at,
                updated_at=policy.updated_at,
                evidence_type='policy',
                owner=policy.owner,
                extension=".policy",
                tags=[TagsInfo(id=tag, name=tag) for tag in policy.tags.all()],
                description=policy.description,
                file=None,
            )
        )
    return policies_mapped


def map_documents_to_evidence_req_attachment(
    documents: list[DriveEvidence], tags_per_doc
) -> list[EvidenceRequestAttachment]:
    evidence_mapped = []
    for d in documents:
        tags = [tpd['tags'] for tpd in tags_per_doc if tpd['id'] == d.evidence.id][0]
        evidence_mapped.append(
            EvidenceRequestAttachment(
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

    return evidence_mapped


def map_attachments_to_drive_evidence_type(
    documents: list[EvidenceRequestAttachment],
) -> list[DriveEvidenceType]:
    attached_documents = []
    for d in documents:
        attached_documents.append(
            DriveEvidenceType(
                id=d.id,
                name=d.name,
                created_at=d.created_at,
                updated_at=d.updated_at,
                evidence_type=d.evidence_type,
                owner=d.owner,
                extension=get_file_extension(d.file.name) if d.file else '',
                tags=d.tags,
                description=d.description,
                file=d.file,
            )
        )

    return attached_documents


def get_comment_mention_users_by_pool(
    audit_id: str, pool: str, user_role: str
) -> list[UserType]:
    lcl_pool_allowed_roles = [AUDITOR, AUDITOR_ADMIN]
    lcl_cx_pool_allowed_roles = [AUDITOR, ROLE_SUPER_ADMIN, AUDITOR_ADMIN]
    laika_pool_allowed_roles = [ROLE_ADMIN, ROLE_SUPER_ADMIN]

    auditors = get_audit_team_and_auditor_admins_mapped_to_usertype(audit_id)
    cxs = get_audit_users_by_role(audit_id, ROLE_SUPER_ADMIN)
    organization_admins = get_audit_users_by_role(audit_id, ROLE_ADMIN)

    if pool == ALL_POOL:
        return auditors + cxs + organization_admins
    elif pool == LCL_POOL and user_role in lcl_pool_allowed_roles:
        return auditors
    elif pool == LCL_CX_POOL and user_role in lcl_cx_pool_allowed_roles:
        return cxs + auditors
    elif pool == LAIKA_POOL and user_role in laika_pool_allowed_roles:
        return cxs + organization_admins

    raise ServiceException("Incorrect user role to perform this action")


def get_comments_count(model: Model, user_role: str, param_filter: Q) -> int:
    auditor_roles = list(AUDITOR_ROLES.values())
    if user_role in auditor_roles:
        pool_filter = Q(pool__in=[ALL_POOL, LCL_POOL, LCL_CX_POOL])
    elif user_role == ROLE_SUPER_ADMIN:
        pool_filter = Q(pool__in=[ALL_POOL, LAIKA_POOL, LCL_CX_POOL])
    else:
        pool_filter = Q(pool__in=[ALL_POOL, LAIKA_POOL])

    comments_count = model.objects.filter(
        param_filter, pool_filter, comment__is_deleted=False
    ).count()

    return comments_count


def build_criteria_table(audit_id: str) -> dict[str, list]:
    criteria_requirement = CriteriaRequirement.objects.filter(
        requirement__audit_id=audit_id, requirement__exclude_in_report=False
    ).annotate(
        display_id_sort=get_display_id_order_annotation(
            preffix='LCL-', field='requirement__display_id'
        )
    )

    criteria_requirement_ids = (
        criteria_requirement.values('criteria_id')
        .annotate(id=Min('id'))
        .values_list('id', flat=True)
    )

    criteria_requirement = criteria_requirement.filter(pk__in=criteria_requirement_ids)

    order_annotate = {
        'criteria_sort': get_order_annotation_char_cast('CC', 'criteria__display_id')
    }
    field = 'criteria_sort'

    order_query = get_order_query(field, 'ascend')

    CC1 = CRITERIAS_TYPE['CONTROL_ENVIRONMENT']
    CC2 = CRITERIAS_TYPE['COMMUNICATION_INFORMATION']
    CC3 = CRITERIAS_TYPE['RISK_ASSESSMENT']
    CC4 = CRITERIAS_TYPE['MONITORING_ACTIVITIES']
    CC5 = CRITERIAS_TYPE['CONTROL_ACTIVITIES']
    CC6 = CRITERIAS_TYPE['LOGICAL_PHYSICAL_ACCESS']
    CC7 = CRITERIAS_TYPE['SYSTEM_OPERATION']
    CC8 = CRITERIAS_TYPE['CHANGE_MANAGEMENT']
    CC9 = CRITERIAS_TYPE['RISK_MITIGATION']
    A1 = CRITERIAS_TYPE['ADDITIONAL_CRITERIA_AVAILABILITY']
    C1 = CRITERIAS_TYPE['ADDITIONAL_CRITERIA_CONFIDENTIALITY']
    PI1 = CRITERIAS_TYPE['ADDITIONAL_CRITERIA_PROCESSING_INTEGRITY']
    P1 = CRITERIAS_TYPE['ADDITIONAL_CRITERIA_PRIVACY']

    control_environment = (
        criteria_requirement.filter(criteria__display_id__startswith=CC1)
        .annotate(**order_annotate)
        .order_by(order_query)
    )
    communication_information = (
        criteria_requirement.filter(criteria__display_id__startswith=CC2)
        .annotate(**order_annotate)
        .order_by(order_query)
    )
    risk_assessment = (
        criteria_requirement.filter(criteria__display_id__startswith=CC3)
        .annotate(**order_annotate)
        .order_by(order_query)
    )
    monitoring_activities = (
        criteria_requirement.filter(criteria__display_id__startswith=CC4)
        .annotate(**order_annotate)
        .order_by(order_query)
    )
    control_activities = (
        criteria_requirement.filter(criteria__display_id__startswith=CC5)
        .annotate(**order_annotate)
        .order_by(order_query)
    )
    logical_physical_access = (
        criteria_requirement.filter(criteria__display_id__startswith=CC6)
        .annotate(**order_annotate)
        .order_by(order_query)
    )
    system_operations = (
        criteria_requirement.filter(criteria__display_id__startswith=CC7)
        .annotate(**order_annotate)
        .order_by(order_query)
    )
    change_management = (
        criteria_requirement.filter(criteria__display_id__startswith=CC8)
        .annotate(**order_annotate)
        .order_by(order_query)
    )
    risk_mitigation = (
        criteria_requirement.filter(criteria__display_id__startswith=CC9)
        .annotate(**order_annotate)
        .order_by(order_query)
    )
    additional_criteria_availability = (
        criteria_requirement.filter(criteria__display_id__startswith=A1)
        .annotate(**order_annotate)
        .order_by(order_query)
    )
    additional_criteria_confidentiality = (
        criteria_requirement.filter(criteria__display_id__startswith=C1)
        .annotate(**order_annotate)
        .order_by(order_query)
    )
    additional_criteria_processing_integrity = (
        criteria_requirement.filter(criteria__display_id__startswith=PI1)
        .annotate(**order_annotate)
        .order_by(order_query)
    )
    additional_criteria_privacy = (
        criteria_requirement.filter(criteria__display_id__startswith=P1)
        .annotate(**order_annotate)
        .order_by(order_query)
    )

    return {
        'control_environment': build_criteria_data_for_report(
            control_environment, audit_id
        ),
        'communication_information': build_criteria_data_for_report(
            communication_information, audit_id
        ),
        'risk_assessment': build_criteria_data_for_report(risk_assessment, audit_id),
        'monitoring_activities': build_criteria_data_for_report(
            monitoring_activities, audit_id
        ),
        'control_activities': build_criteria_data_for_report(
            control_activities, audit_id
        ),
        'logical_physical_access': build_criteria_data_for_report(
            logical_physical_access, audit_id
        ),
        'system_operations': build_criteria_data_for_report(
            system_operations, audit_id
        ),
        'change_management': build_criteria_data_for_report(
            change_management, audit_id
        ),
        'risk_mitigation': build_criteria_data_for_report(risk_mitigation, audit_id),
        'additional_criteria_availability': build_criteria_data_for_report(
            additional_criteria_availability, audit_id
        ),
        'additional_criteria_confidentiality': build_criteria_data_for_report(
            additional_criteria_confidentiality, audit_id
        ),
        'additional_criteria_processing_integrity': build_criteria_data_for_report(
            additional_criteria_processing_integrity, audit_id
        ),
        'additional_criteria_privacy': build_criteria_data_for_report(
            additional_criteria_privacy, audit_id
        ),
    }


def create_public_link(attachment, organization):
    url = attachment.file.url
    name = attachment.name
    extension = get_file_extension(name)
    extensions = list(WORD_DOCUMENT_EXTENSION.values())
    if extension in extensions:
        logger.info(f'Generating public url for: {url}')
        url_file = url.split('?')[0]

        link_qs = Link.objects.filter(
            url__istartswith=url_file, organization=organization
        )
        exist = link_qs.exists()
        if not exist:
            public_url = Link.objects.create(
                organization=organization,
                url=url,
                expiration_date=None,
                is_enabled=True,
            ).public_url
            logger.info(f'Public url created: {public_url}')
            return public_url

        link = link_qs.first()
        link.url = url
        link.save(update_fields=['url'])

        public_url = link.public_url
        logger.info(f'Public url updated: {public_url}')
        return public_url
    return url
