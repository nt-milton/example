import base64
import io
import tempfile
from unittest.mock import Mock, patch

import pytest
from django.core.files import File
from django.db.models import Q, TextField, Value
from django.db.models.functions import Cast

from alert.tests.factory import create_evidence
from audit.constants import AUDIT_FIRMS
from audit.models import Audit, AuditAuditor, AuditFirm, Organization
from audit.tests.factory import create_audit, create_audit_firm
from comment.models import Comment
from drive.models import DriveEvidence, DriveEvidenceData
from drive.types import DriveEvidenceType
from evidence.constants import LAIKA_PAPER
from fieldwork.constants import (
    ALL_POOL,
    ER_STATUS_DICT,
    LAIKA_POOL,
    LCL_CX_POOL,
    LCL_POOL,
    LO_FILE_TYPES,
    MONITOR_FILE_NAMES,
    POLICY_FETCH_TYPE,
    POLICY_SOURCE_TYPE,
)
from fieldwork.util.evidence_request import (
    file_attachment_match_name,
    store_er_attachments_metrics,
)
from fieldwork.utils import (
    add_evidence_attachment,
    map_attachments_to_drive_evidence_type,
    map_documents_to_evidence_req_attachment,
    map_policies_to_evidence_req_attachment,
)
from integration.models import PAYROLL, PROJECT_MANAGEMENT
from laika.utils.exceptions import ServiceException
from link.models import Link
from monitor.tests.factory import (
    create_monitor,
    create_monitor_result,
    create_organization_monitor,
)
from organization.tests import create_organization
from policy.tests.factory import create_published_empty_policy
from user.constants import AUDITOR, AUDITOR_ADMIN, ROLE_ADMIN, ROLE_SUPER_ADMIN
from user.models import Auditor, User
from user.tests import create_user
from user.tests.factory import create_user_auditor
from vendor.models import Vendor

from ..models import (
    AttachmentSourceType,
    Criteria,
    CriteriaRequirement,
    EvidenceComment,
    EvidenceMetric,
    Requirement,
    TemporalAttachment,
)
from ..util.evidence_attachment import (
    create_file_for_monitor,
    get_attachment_source_type,
)
from ..utils import (
    EVIDENCE_ATTACHMENT_FIELD,
    attachment_query_exist,
    build_criteria_data_for_report,
    build_criteria_table,
    create_policies_tmp_attachments,
    create_public_link,
    format_value,
    get_audit_team_and_auditor_admins,
    get_audit_team_and_auditor_admins_mapped_to_usertype,
    get_comments_count,
    get_sso_cloud_provider,
    get_sso_cloud_providers_quantity,
    get_trust_service_categories,
    update_evidence_status,
)


@pytest.fixture
def organization() -> Organization:
    return create_organization()


@pytest.fixture
def user(organization: Organization) -> User:
    return create_user(organization)


@pytest.fixture
def audit_firm() -> AuditFirm:
    return create_audit_firm(AUDIT_FIRMS[0])


@pytest.fixture
def tmp_attachment(audit: Audit):
    TemporalAttachment.objects.create(
        file=File(file=tempfile.TemporaryFile(), name='test.pdf'), audit=audit
    )


@pytest.fixture
def audit(organization: Organization, audit_firm: AuditFirm) -> Audit:
    return create_audit(
        organization=organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021',
        audit_firm=audit_firm,
    )


@pytest.fixture
def criteria() -> Criteria:
    return Criteria.objects.create(display_id='CC1.1', description='yyy')


@pytest.fixture
def requirement(audit: Audit) -> Requirement:
    return Requirement.objects.create(
        audit=audit, display_id='LCL-1', description='zzz'
    )


@pytest.fixture
def criteria_requirement(
    criteria: Criteria, requirement: Requirement
) -> CriteriaRequirement:
    return CriteriaRequirement.objects.create(
        criteria=criteria, requirement=requirement
    )


@pytest.fixture
def organization_monitor(organization):
    return create_organization_monitor(
        organization=organization,
        monitor=create_monitor(name='Monitor Test', query='select name from test'),
    )


@pytest.fixture
def auditor_user_in_audit_team(audit_firm: AuditFirm, audit: Audit) -> Auditor:
    auditor = create_user_auditor(
        email='auditor_user_in_team@heylaika.com',
        role=AUDITOR,
        with_audit_firm=True,
        audit_firm=audit_firm.name,
    )

    AuditAuditor.objects.create(auditor=auditor, audit=audit)
    return auditor


@pytest.fixture
def auditor_user_not_in_audit_team(audit_firm: AuditFirm, audit: Audit) -> Auditor:
    return create_user_auditor(
        email='auditor_user_not_in_team@heylaika.com',
        role=AUDITOR,
        with_audit_firm=True,
        audit_firm=audit_firm.name,
    )


@pytest.fixture
def auditor_admin_user(audit_firm: AuditFirm) -> Auditor:
    return create_user_auditor(
        email='auditoradmin@heylaika.com',
        role=AUDITOR_ADMIN,
        with_audit_firm=True,
        audit_firm=audit_firm.name,
    )


@pytest.fixture
def policy_1(organization, user):
    return create_published_empty_policy(organization=organization, user=user)


@pytest.fixture
def policy_2(organization, user):
    return create_published_empty_policy(organization=organization, user=user)


@pytest.fixture
def drive_evidence_laikapaper(organization, user):
    file = File(file=tempfile.TemporaryFile(), name='Laikapaper File')
    drive_evidence_data = DriveEvidenceData(
        type=LAIKA_PAPER,
        file=file,
    )
    return DriveEvidence.objects.custom_create(
        organization=organization, owner=user, drive_evidence_data=drive_evidence_data
    )


@pytest.fixture
def evidence(audit):
    return create_evidence(audit)


@pytest.fixture
def evidence_with_attachment(graphql_organization, audit):
    evidence = create_evidence(audit)
    create_evidence_attachment(graphql_organization, evidence)

    return evidence


@pytest.fixture
def comment(graphql_user):
    comment = Comment.objects.create(owner=graphql_user, content='Dummy comment')
    return comment


@pytest.mark.functional
@pytest.mark.skipif(
    True,
    reason='''We can not test this because sqlite3
                                    does not support regex operations''',
)
def test_build_criteria_data_for_report(
    criteria_requirement: CriteriaRequirement, audit: Audit
):
    criteria = build_criteria_data_for_report([criteria_requirement], audit.id)
    assert len(criteria) == 1
    assert criteria[0]['display_id'] == 'CC 1.1'
    assert len(criteria[0]['requirements']) == 1
    assert criteria[0]['requirements'][0]['display_id'] == 'LCL-1'


@pytest.mark.functional
def test_get_sso_cloud_provider_quantity(organization: Organization):
    assert get_sso_cloud_providers_quantity(organization) == 0

    vendor = Vendor.objects.create(
        name='AWS',
    )
    vendor.organizations.add(organization)
    vendor = Vendor.objects.create(
        name='Heroku',
    )
    vendor.organizations.add(organization)

    assert get_sso_cloud_providers_quantity(organization) == 2


@pytest.mark.functional
def test_get_sso_cloud_provider(organization: Organization):
    assert get_sso_cloud_provider(organization) == 'sso_cloud_provider'

    vendor = Vendor.objects.create(
        name='AWS',
    )
    vendor.organizations.add(organization)
    vendor = Vendor.objects.create(
        name='Heroku',
    )
    vendor.organizations.add(organization)

    assert get_sso_cloud_provider(organization) == 'AWS and Heroku'


@pytest.mark.parametrize(
    "list, result",
    [
        (['Heroku, AWS, Google Cloud'], 'Heroku, AWS and Google Cloud'),
        (['AA', 'BB'], 'AA and BB'),
        (['Apple'], 'Apple'),
        ([], ''),
    ],
)
@pytest.mark.functional
def test_get_trust_service_categories(list: list, result: str):
    assert get_trust_service_categories(list) == result


@pytest.mark.parametrize(
    "filters, result",
    [
        ([{'field': EVIDENCE_ATTACHMENT_FIELD, 'value': 'xx', 'operator': 'xx'}], True),
        ([{'field': 'xxxx', 'value': 'xx', 'operator': 'xx'}], False),
    ],
)
def test_attachment_query_exist(filters, result):
    assert attachment_query_exist(filters) == result


@pytest.mark.functional
def test_format_value_user_type():
    val = format_value('sss@heylaika.com,aaa@heylaika.com', 'USER')
    assert val == ['sss@heylaika.com', 'aaa@heylaika.com']


@pytest.mark.functional
def test_format_value_true_type():
    val = format_value('true', '')
    assert val is True


@pytest.mark.functional
def test_format_value_false_type():
    val = format_value('false', '')
    assert val is False


@pytest.mark.functional
def test_create_tmp_policies_attachments(organization, audit):
    create_policies_tmp_attachments(audit, [])
    assert len(TemporalAttachment.objects.filter(audit=audit)) == 0


@pytest.mark.functional
def test_create_file_for_monitor(organization_monitor):
    create_monitor_result(
        organization_monitor=organization_monitor,
        result={'columns': ['id'], 'data': []},
    )
    file_name, file = create_file_for_monitor(
        organization_monitor.id, organization_monitor.name, 'UTC'
    )
    assert file_name.index(organization_monitor.name) != -1


@pytest.mark.functional
def test_get_audit_team_and_auditor_admins(
    auditor_admin_user,
    auditor_user_not_in_audit_team,
    auditor_user_in_audit_team,
    audit,
):
    assert len(get_audit_team_and_auditor_admins(audit.id)) == 2


@pytest.mark.functional
def test_get_audit_team_and_auditor_admins_mapped_to_usertype(
    auditor_admin_user,
    auditor_user_not_in_audit_team,
    auditor_user_in_audit_team,
    audit,
):
    assert len(get_audit_team_and_auditor_admins_mapped_to_usertype(audit.id)) == 2


@pytest.mark.functional
def test_map_policies_to_evidence_req_attachment(policy_1, policy_2):
    attachments = map_policies_to_evidence_req_attachment([policy_1, policy_2])

    assert len(attachments) == 2
    assert attachments[0].evidence_type == 'policy'


@pytest.mark.functional
def test_map_documents_to_evidence_req_attachment(drive_evidence_laikapaper):
    attachments = map_documents_to_evidence_req_attachment(
        [drive_evidence_laikapaper], [{'id': drive_evidence_laikapaper.id, 'tags': []}]
    )

    assert len(attachments) == 1


@pytest.mark.functional
def test_map_attachments_to_drive_evidence_type(policy_1, policy_2):
    attachments = map_policies_to_evidence_req_attachment([policy_1, policy_2])
    attachments_mapped = map_attachments_to_drive_evidence_type(attachments)

    assert len(attachments_mapped) == 2
    assert attachments_mapped[0].evidence_type == 'policy'
    assert isinstance(attachments_mapped[0], DriveEvidenceType)


@pytest.mark.functional
def test_get_comments_count_when_user_is_auditor_admin(evidence, comment):
    pools = [ALL_POOL, LCL_POOL, LCL_CX_POOL]
    create_comment_in_pools(pools, evidence, comment)
    role = AUDITOR_ADMIN
    param_filter = Q(evidence=evidence)
    comments_count = get_comments_count(EvidenceComment, role, param_filter)

    assert comments_count == len(pools)


@pytest.mark.functional
def test_get_comments_count_when_user_is_auditor(evidence, comment):
    pools = [ALL_POOL, LCL_POOL, LCL_CX_POOL]
    create_comment_in_pools(pools, evidence, comment)
    role = AUDITOR
    param_filter = Q(evidence=evidence)
    comments_count = get_comments_count(EvidenceComment, role, param_filter)

    assert comments_count == len(pools)


@pytest.mark.functional
def test_should_not_get_comments_count_from_laika_pool_for_auditor_admin(
    evidence, comment
):
    EvidenceComment.objects.create(evidence=evidence, comment=comment, pool=LAIKA_POOL)
    role = AUDITOR_ADMIN
    param_filter = Q(evidence=evidence)
    comments_count = get_comments_count(EvidenceComment, role, param_filter)

    assert comments_count == 0


@pytest.mark.functional
def test_should_not_get_comments_count_from_laika_pool_for_auditor(evidence, comment):
    pools = [LCL_CX_POOL, LAIKA_POOL]
    create_comment_in_pools(pools, evidence, comment)
    role = AUDITOR_ADMIN
    param_filter = Q(evidence=evidence)
    comments_count = get_comments_count(EvidenceComment, role, param_filter)

    assert comments_count == 1


@pytest.mark.functional
def test_get_comments_count_when_user_is_super_admin(evidence, comment):
    pools = [ALL_POOL, LAIKA_POOL, LCL_CX_POOL]
    create_comment_in_pools(pools, evidence, comment)
    role = ROLE_SUPER_ADMIN
    param_filter = Q(evidence=evidence)
    comments_count = get_comments_count(EvidenceComment, role, param_filter)

    assert comments_count == len(pools)


@pytest.mark.functional
def test_should_not_get_comments_count_from_lcl_pool_for_super_admin(evidence, comment):
    pools = [LCL_POOL, LAIKA_POOL]
    create_comment_in_pools(pools, evidence, comment)
    role = AUDITOR_ADMIN
    param_filter = Q(evidence=evidence)
    comments_count = get_comments_count(EvidenceComment, role, param_filter)

    assert comments_count == 1


@pytest.mark.functional
def test_get_comments_count_for_any_other_role(evidence, comment):
    pools = [ALL_POOL, LAIKA_POOL, LCL_CX_POOL]
    create_comment_in_pools(pools, evidence, comment)
    role = 'ANY OTHER THAN SUPER_ADMIN OR AUDITOR'
    param_filter = Q(evidence=evidence)
    comments_count = get_comments_count(EvidenceComment, role, param_filter)

    assert comments_count == 2


@pytest.mark.functional
@pytest.mark.parametrize(
    "new_status, is_reviewed",
    [
        (ER_STATUS_DICT['Pending'], False),
        (ER_STATUS_DICT['Submitted'], True),
    ],
)
def test_update_evidence_status_super_admin(
    evidence_with_attachment, graphql_user, new_status, is_reviewed
):
    graphql_user.role = ROLE_SUPER_ADMIN
    graphql_user.save()
    evidence_status = update_evidence_status(
        [evidence_with_attachment], new_status, graphql_user
    )

    updated_evidence = evidence_status[0]
    assert updated_evidence.status == new_status
    assert updated_evidence.is_laika_reviewed == is_reviewed


@pytest.mark.functional
@pytest.mark.parametrize(
    "new_status, is_reviewed",
    [
        (ER_STATUS_DICT['Pending'], False),
        (ER_STATUS_DICT['Submitted'], False),
    ],
)
def test_update_evidence_status_admin_user(
    evidence_with_attachment, graphql_user, new_status, is_reviewed
):
    graphql_user.role = ROLE_ADMIN
    graphql_user.save()
    evidence_status = update_evidence_status(
        [evidence_with_attachment], new_status, graphql_user
    )

    updated_evidence = evidence_status[0]
    assert updated_evidence.status == new_status
    assert updated_evidence.is_laika_reviewed == is_reviewed


@pytest.mark.functional
def test_update_evidence_status_no_attachments(evidence, graphql_user):
    with pytest.raises(ServiceException) as exception_info:
        update_evidence_status([evidence], ER_STATUS_DICT['Submitted'], graphql_user)

    assert (
        str(exception_info.value)
        == f'Evidence selected: {evidence.display_id} must have at least one attachment'
    )


def create_evidence_attachment(
    organization, evidence, sample_id=None, file_name='attachment'
):
    txt_file = 'This is a simple attachment'
    base64_file_bytes = base64.b64encode(txt_file.encode('ascii'))
    base64_file_message = base64_file_bytes.decode('ascii')
    message_encode = base64_file_message.encode('ascii')
    uploaded_files = [
        File(name=file_name, file=io.BytesIO(base64.b64decode(message_encode)))
    ]
    policies = []
    documents = []
    officers = []
    teams = []
    objects_ids = []
    monitors = []
    vendors = []
    trainings = []

    return add_evidence_attachment(
        evidence,
        policies,
        uploaded_files,
        documents,
        officers,
        teams,
        objects_ids,
        monitors,
        vendors,
        trainings,
        organization=organization,
        time_zone=None,
        sample_id=sample_id,
    )


def multiline_to_singleline(multiline):
    return ' '.join(multiline.split())


def create_comment_in_pools(pools, evidence, comment):
    for pool in pools:
        EvidenceComment.objects.create(evidence=evidence, comment=comment, pool=pool)


@pytest.mark.django_db
def test_file_attachment_match_monitor(graphql_organization):
    result = file_attachment_match_name(
        '[Policies] Information Security Policy Published in Laika_123.pdf',
        MONITOR_FILE_NAMES,
    )
    assert result is True


@pytest.mark.django_db
def test_file_attachment_monitor_dont_match():
    result = file_attachment_match_name(
        'Security Policy Published in Laik_123.pdf', MONITOR_FILE_NAMES
    )
    assert result is False


@pytest.mark.django_db
def test_store_er_attachments_new_metrics(evidence, er_metrics):
    monitors_count = 1
    file_monitors_count = 3
    file_integration_count = 5
    integrations_category_counter = {PROJECT_MANAGEMENT: 1, PAYROLL: 2}
    store_er_attachments_metrics(
        er_metrics,
        monitors_count,
        file_monitors_count,
        file_integration_count,
        integrations_category_counter,
    )
    expected_monitors_count = 6
    current_monitors_count = (
        EvidenceMetric.objects.filter(evidence_request=evidence).first().monitors_count
    )

    expected_integrations_counter = {'general': 7, PROJECT_MANAGEMENT: 2, PAYROLL: 3}
    current_integrations_counter = (
        EvidenceMetric.objects.filter(evidence_request=evidence)
        .first()
        .integrations_counter
    )

    assert expected_monitors_count == current_monitors_count
    assert (
        expected_integrations_counter['general']
        == current_integrations_counter['general']
    )
    assert (
        expected_integrations_counter[PROJECT_MANAGEMENT]
        == current_integrations_counter[PROJECT_MANAGEMENT]
    )
    assert (
        expected_integrations_counter[PAYROLL] == current_integrations_counter[PAYROLL]
    )


@pytest.mark.django_db
def test_store_er_attachments_no_new_metrics(evidence, er_metrics):
    store_er_attachments_metrics(er_metrics)
    expected_monitors_count = 2
    current_monitors_count = (
        EvidenceMetric.objects.filter(evidence_request=evidence).first().monitors_count
    )

    expected_integrations_counter = {'general': 2, PROJECT_MANAGEMENT: 1, PAYROLL: 1}
    current_integrations_counter = (
        EvidenceMetric.objects.filter(evidence_request=evidence)
        .first()
        .integrations_counter
    )

    assert expected_monitors_count == current_monitors_count
    assert (
        expected_integrations_counter['general']
        == current_integrations_counter['general']
    )
    assert (
        expected_integrations_counter[PROJECT_MANAGEMENT]
        == current_integrations_counter[PROJECT_MANAGEMENT]
    )
    assert (
        expected_integrations_counter[PAYROLL] == current_integrations_counter[PAYROLL]
    )


@pytest.mark.django_db
def test_file_attachment_match_lo(graphql_organization):
    result = file_attachment_match_name(
        'SWARMIA_PULL_REQUEST_2021_09_25_17_30.xlsx', LO_FILE_TYPES
    )
    assert result is True


@pytest.mark.django_db
def test_file_attachment_lo_dont_match():
    result = file_attachment_match_name(
        'Security Policy Published in Laik_123.pdf', LO_FILE_TYPES
    )
    assert result is False


@pytest.mark.django_db
def test_get_attachment_source_if_type_exists(attachment_source_types):
    expected_source = get_attachment_source_type(POLICY_FETCH_TYPE)
    assert expected_source.name == POLICY_SOURCE_TYPE
    assert AttachmentSourceType.objects.filter(name=POLICY_SOURCE_TYPE).count() == 1


@pytest.mark.django_db
def test_get_attachment_source_if_type_not_exists(attachment_source_types):
    new_type = 'new_type'
    expected_source = get_attachment_source_type(new_type)
    assert expected_source.name == new_type


@pytest.mark.django_db
@patch(
    'fieldwork.utils.get_display_id_order_annotation',
    return_value=Cast(Value('LCL-1'), output_field=TextField()),
)
@patch(
    'fieldwork.utils.get_order_annotation_char_cast',
    return_value=Cast(Value('CC1.1'), output_field=TextField()),
)
def test_build_criteria_table(
    get_display_id_order_annotation_mock,
    get_order_annotation_char_cast,
    criteria_requirement: CriteriaRequirement,
    audit: Audit,
):
    criteria = build_criteria_table(audit.id)
    control_environment = criteria['control_environment']

    assert len(control_environment) == 1
    assert control_environment[0]['display_id'] == 'CC1.1'
    assert control_environment[0]['description'] == 'yyy'
    assert control_environment[0]['requirements'][0]['display_id'] == 'LCL-1'
    assert control_environment[0]['requirements'][0]['description'] == 'zzz'


@pytest.mark.django_db
@patch(
    'fieldwork.utils.get_display_id_order_annotation',
    return_value=Cast(Value('LCL-1'), output_field=TextField()),
)
@patch(
    'fieldwork.utils.get_order_annotation_char_cast',
    return_value=Cast(Value('CC1.1'), output_field=TextField()),
)
def test_build_criteria_table_excluding_requirements(
    get_display_id_order_annotation_mock,
    get_order_annotation_char_cast,
    criteria_requirement: CriteriaRequirement,
    audit: Audit,
):
    criteria_requirement.requirement.exclude_in_report = True
    criteria_requirement.requirement.save()
    criteria = build_criteria_table(audit.id)
    control_environment = criteria['control_environment']

    assert len(control_environment) == 0


@pytest.mark.parametrize('file, create_new', [('file.doc', False), ('file.docx', True)])
@pytest.mark.django_db
def test_create_public_link(file, create_new, graphql_organization):
    url = f'http://www.laika.com/{file}'

    if create_new:
        Link.objects.create(organization=graphql_organization, url=url)

    mock_attachment = Mock()
    mock_attachment.name = file
    mock_attachment.file.url = url

    public_url = create_public_link(mock_attachment, graphql_organization)

    link_qs = Link.objects.filter(url=url)
    assert link_qs.count() == 1
    assert public_url != url


@pytest.mark.django_db
@pytest.mark.parametrize('file', ['file.pdf', 'file.xls', 'file.csv', 'file.ppt'])
def test_create_public_link_not_word_document(file, graphql_organization):
    url = f'http://www.laika.com/{file}'

    mock_attachment = Mock()
    mock_attachment.name = file
    mock_attachment.file.url = url

    public_url = create_public_link(mock_attachment, graphql_organization)

    assert not Link.objects.filter(url=url).exists()
    assert public_url == url
