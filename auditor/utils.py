from django.db.models import Case, F, IntegerField, Q, QuerySet, Value, When
from django.db.models.functions import Cast, Replace

from audit.constants import CURRENT_AUDIT_STATUS
from audit.models import Audit, AuditAuditor, AuditorAuditFirm
from audit.utils.audit import get_current_status
from fieldwork.constants import (
    CRITERIAS_PREFFIXES,
    EVIDENCE_ATTRIBUTES,
    EXCEPTION_NOTED,
    NO_EXCEPTIONS_NOTED,
    NOT_TESTED,
    REQ_STATUS_DICT,
)
from fieldwork.models import Criteria, Requirement, RequirementStatusTransition, Test
from fieldwork.utils import (
    format_value,
    get_display_id_order_annotation,
    get_fieldwork_state_filtered,
    get_order_annotation_char_cast,
    get_order_info,
)
from laika.utils.exceptions import ServiceException
from laika.utils.query_builder import get_incredible_filter_query
from user.models import Auditor


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


EVIDENCE_ATTACHMENT_FIELD = 'attachments_num'


def attachment_query_exist(filters):
    attachment_filter = [
        filter for filter in filters if filter['field'] == EVIDENCE_ATTACHMENT_FIELD
    ]
    return True if len(attachment_filter) > 0 else False


def get_requirements_by_args(kwargs):
    (filter, field, order_annotate, order, search_criteria) = get_order_info(kwargs)

    audit_id = kwargs.get('audit_id')
    requirement_qs = get_fieldwork_state_filtered(
        filters=filter, state_qs=Requirement.objects.all(), audit_id=audit_id
    )

    if field == 'display_id':
        order_annotate = {
            'display_id_sort': get_display_id_order_annotation(preffix='LCL-')
        }
        field = 'display_id_sort'

    order_query = (
        F(field).desc(nulls_last=True)
        if order == 'descend'
        else F(field).asc(nulls_last=True)
    )

    if search_criteria:
        requirement_qs = requirement_qs.filter(
            Q(display_id__icontains=search_criteria)
            | Q(name__icontains=search_criteria)
        )

    status = kwargs.get('status')

    if status:
        return (
            requirement_qs.filter(
                status__iexact=status, audit__id=audit_id, is_deleted=False
            )
            .distinct()
            .annotate(**order_annotate)
            .order_by(order_query)
        )

    return (
        requirement_qs.filter(audit__id=audit_id, is_deleted=False)
        .distinct()
        .annotate(**order_annotate)
        .order_by(order_query)
    )


def get_requirement_tests(requirement):
    requirement_test = (
        Test.objects.filter(requirement_id=requirement.id, is_deleted=False)
        .annotate(display_id_sort=get_display_id_order_annotation(preffix='Test-'))
        .annotate(
            formatted_result=Case(
                When(result='exceptions_noted', then=Value(EXCEPTION_NOTED)),
                When(result='no_exceptions_noted', then=Value(NO_EXCEPTIONS_NOTED)),
                When(result='not_tested', then=Value(NOT_TESTED)),
                default=Value('Pending result'),
            )
        )
        .order_by('display_id_sort')
    )
    return requirement_test


def get_criteria_by_args(search_criteria, query_set):
    if search_criteria:
        return query_set.filter(
            Q(criteria__display_id__icontains=search_criteria)
            | Q(criteria__description__icontains=search_criteria)
        )

    return query_set


def is_auditor_associated_to_audit_firm(audit, auditor_id):
    return AuditorAuditFirm.objects.filter(
        audit_firm_id=audit.audit_firm.id, auditor_id=auditor_id
    ).exists()


def assign_requirement_user(input, user_type, updated_timestamp):
    requirement_ids = input.get('requirement_ids')
    email = input.get('email')
    audit_id = input.get('audit_id')
    timestamp_field = f'{user_type}_updated_at'

    auditor_qs = Auditor.objects.filter(
        user__email=email,
    )
    auditor = auditor_qs.first()

    requirement_list = Requirement.objects.filter(
        id__in=requirement_ids, audit_id=audit_id
    )

    new_requirements = []
    for requirement in requirement_list:
        setattr(requirement, user_type, auditor)
        setattr(requirement, timestamp_field, updated_timestamp)
        new_requirements.append(requirement)

    Requirement.objects.bulk_update(new_requirements, [user_type, timestamp_field])

    return new_requirements


def validate_requirement_complete_status_change(user, audit, requirement_ids):
    if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
        raise ServiceException(
            """
            Requirements can only be marked as complete
            by a member of the Audit Firm
            """
        )

    if user.role != 'AuditorAdmin':
        is_auditor_reviewer_or_lead_auditor = AuditAuditor.objects.filter(
            audit=audit,
            auditor__user__email=user.email,
            title_role__in=['lead_auditor', 'reviewer'],
        ).exists()

        if not is_auditor_reviewer_or_lead_auditor:
            raise ServiceException(
                """
                Requirements can only be marked as complete by a
                Reviewer, Lead Auditor or Admin
                """
            )

    incomplete_tests = Test.objects.filter(
        Q(requirement_id__in=requirement_ids, is_deleted=False)
        & Q(result__in=['exceptions_noted', 'not_tested'])
        & (Q(notes__exact='') | Q(notes__isnull=True))
    )

    if incomplete_tests.exists():
        raise ServiceException(
            f'''{incomplete_tests[0].requirement.display_id}:
            Tests with Exceptions Noted or Not Tested must have notes'''
        )

    return True


def validate_requirement_status_change(old_status, new_status):
    invalid_updates = [
        ('open', 'completed'),
    ]
    current_change = (old_status, new_status.lower())
    if current_change in invalid_updates:
        raise ServiceException(
            f'Invalid requirement status update: {old_status} to {new_status}'
        )


def update_requirements_status(requirements, status, user):
    validate_requirement_status_change(requirements[0].status, status)
    new_requirements = []
    for req in requirements:
        to_status_is_open = status == REQ_STATUS_DICT['Open']
        is_not_already_open = req.status != REQ_STATUS_DICT['Open']
        if to_status_is_open and is_not_already_open:
            req.times_moved_back_to_open += 1
        RequirementStatusTransition.objects.create(
            from_status=req.status,
            to_status=status,
            requirement=req,
            status_updated_by=user,
        )
        req.status = status
        new_requirements.append(req)

    return new_requirements


def validate_auditor_get_draft_report_file(audit: Audit):
    audit_status = audit.status.first()
    allowed_status = [
        CURRENT_AUDIT_STATUS['FIELDWORK'],
        CURRENT_AUDIT_STATUS['IN_DRAFT_REPORT'],
        CURRENT_AUDIT_STATUS['COMPLETED'],
    ]
    current_status = get_current_status(audit_status)
    if current_status not in allowed_status:
        raise ServiceException("Invalid audit stage to return a draft report file")
    if not audit_status.draft_report_file_generated:
        raise ServiceException("Audit draft report file hasn't been generated yet")


def increment_display_id(model, audit_id: str, reference: str) -> str:
    query = model.objects.filter(audit_id=audit_id)
    return get_next_display_id(query, reference)


def get_next_display_id(query, reference: str) -> str:
    last_display_id_number = (
        query.annotate(
            display_number=Cast(
                Replace('display_id', Value(f'{reference}-'), Value('')),
                output_field=IntegerField(),
            )
        )
        .order_by('display_number')
        .values_list('display_number', flat=True)
        .last()
    )
    if last_display_id_number:
        return f'{reference}-{str(last_display_id_number+1)}'
    else:
        return f'{reference}-1'


def get_criteria_by_audit_id(audit_id: str) -> QuerySet[Criteria]:
    CC, A, C, P = CRITERIAS_PREFFIXES.values()
    field = 'display_id'
    field_to_sort = 'criteria_sort'
    cc_order_annotate = {'criteria_sort': get_order_annotation_char_cast(CC, field)}
    a_order_annotate = {'criteria_sort': get_order_annotation_char_cast(A, field)}
    c_order_annotate = {'criteria_sort': get_order_annotation_char_cast(C, field)}
    p_order_annotate = {'criteria_sort': get_order_annotation_char_cast(P, field)}

    criteria = Criteria.objects.filter(audit_id=audit_id)
    if criteria.count() == 0:
        criteria = Criteria.objects.filter(audit_id=None)

    cc_criteria = (
        criteria.filter(display_id__startswith=CC)
        .annotate(**cc_order_annotate)
        .order_by(F(field_to_sort).asc())
    )

    a_criteria = (
        criteria.filter(display_id__startswith=A)
        .annotate(**a_order_annotate)
        .order_by(F(field_to_sort).asc())
    )

    c_criteria = (
        criteria.filter(display_id__startswith=C)
        .exclude(display_id__startswith=CC)
        .annotate(**c_order_annotate)
        .order_by(F(field_to_sort).asc())
    )

    p_criteria = (
        criteria.filter(display_id__startswith=P)
        .annotate(**p_order_annotate)
        .order_by(F(field_to_sort).asc())
    )

    return cc_criteria | a_criteria | c_criteria | p_criteria
