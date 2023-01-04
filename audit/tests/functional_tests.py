import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from alert.constants import ALERT_TYPES
from audit.constants import AUDIT_TYPES, CURRENT_AUDIT_STATUS, TITLE_ROLES
from audit.models import (
    Audit,
    AuditAlert,
    AuditAuditor,
    AuditStatus,
    AuditStepTimestamp,
)
from audit.tests.constants import (
    CRITERIA_MOCK_DATA,
    HITRUST,
    SOC_2_TYPE_1,
    SOC_2_TYPE_2,
)
from feature.models import AuditorFlag
from fieldwork.models import Requirement
from user.admin import User
from user.constants import AUDITOR, AUDITOR_ADMIN
from user.models import Auditor
from user.tests import create_user_auditor

from .factory import (
    associate_organization_audit_firm,
    create_audit,
    create_audit_framework_type,
    create_audit_status,
    create_coupon,
    get_framework_type_from_key,
)
from .mutations import (
    ASSIGN_AUDIT_TO_AUDITOR,
    AUDITOR_UPDATE_AUDIT_CONTENT_STEP,
    AUDITOR_UPDATE_AUDIT_DETAILS,
    AUDITOR_UPDATE_AUDIT_STAGE,
    CHECK_AUDIT_STATUS_FIELD,
    CREATE_AUDIT,
    DELETE_AUDITOR_USERS,
    REMOVE_AUDITOR_FROM_AUDIT,
    UPDATE_AUDIT_STAGE,
    UPDATE_AUDITOR,
    UPDATE_AUDITOR_ROLE_IN_AUDIT_TEAM,
    UPDATE_AUDITOR_USER_PREFERENCES,
)
from .queries import (
    GET_ALL_ONGOING_AUDITS,
    GET_AUDIT,
    GET_AUDIT_TEAM,
    GET_AUDIT_TYPES,
    GET_AUDITOR_AUDIT,
    GET_AUDITOR_ONGOING_AUDITS,
    GET_AUDITOR_PAST_AUDITS,
    GET_AUDITOR_USER,
    GET_AUDITOR_USERS,
    GET_AUDITORS,
    GET_AUDITS_IN_PROGRESS,
    GET_PAST_AUDITS,
)

AUDIT_NAME = 'Laika Dev Soc 2 Type 1 Audit 2021'
LEAD_AUDITOR = 'Lead Auditor'
TESTER = 'Tester'
REVIEWER = 'Reviewer'
AUDIT_CONFIGURATION = (
    '{"as_of_date": "2022-12-20", "trust_services_categories": ["Security"]}'
)

SOC_2_TYPE_1_NAME = 'SOC 2 Type 1'
SOC_2_TYPE_2_NAME = 'SOC 2 Type 2'


@pytest.fixture
def admin_auditor_user(graphql_audit_firm):
    return create_user_auditor(
        email='johndoe@heylaika.com',
        role=AUDITOR_ADMIN,
        with_audit_firm=True,
        audit_firm=graphql_audit_firm.name,
        user_preferences={"profile": {"alerts": "Daily", "emails": "Daily"}},
    )


@pytest.fixture
def soc2_type1_audit_framework_type(graphql_organization):
    return create_audit_framework_type(
        organization=graphql_organization, audit_type_key=SOC_2_TYPE_1
    )


@pytest.fixture
def soc2_type2_audit_framework_type(graphql_organization):
    return create_audit_framework_type(
        organization=graphql_organization, audit_type_key=SOC_2_TYPE_2
    )


@pytest.fixture
def hitrust_audit_framework_type(graphql_organization):
    return create_audit_framework_type(
        organization=graphql_organization, audit_type_key=HITRUST, unlocked=False
    )


@pytest.fixture
def soc2_type1_coupon(graphql_organization, graphql_audit_firm):
    framework_type = get_framework_type_from_key(SOC_2_TYPE_1)
    return create_coupon(
        graphql_organization,
        coupon_type=f'{framework_type} {graphql_audit_firm.name}',
        coupon_count=10,
    )


@pytest.fixture
def soc2_type1_no_coupons(graphql_organization, graphql_audit_firm):
    framework_type = get_framework_type_from_key(SOC_2_TYPE_1)
    return create_coupon(
        graphql_organization,
        coupon_type=f'{framework_type} {graphql_audit_firm.name}',
        coupon_count=0,
    )


@pytest.fixture
def organization_audit_firm(graphql_organization, graphql_audit_firm):
    return associate_organization_audit_firm(graphql_organization, graphql_audit_firm)


@pytest.fixture
def auditor():
    return create_user_auditor(
        with_audit_firm=False,
        email='kevin@heylaika.com',
        role=AUDITOR_ADMIN,
        first_name='Kevin',
        last_name='Test',
        user_preferences={"profile": {"alerts": "Never", "emails": "Daily"}},
    )


@pytest.fixture
def auditor2():
    return create_user_auditor(
        with_audit_firm=False,
        email='adam@heylaika.com',
        role=AUDITOR,
        first_name='Adam',
        last_name='Test',
        user_preferences={"profile": {"alerts": "Never", "emails": "Daily"}},
    )


@pytest.fixture
def auditor_with_firm_2(graphql_audit_firm):
    return create_user_auditor(
        email='annie@heylaika.com',
        role=AUDITOR,
        first_name='Annie',
        last_name='Test',
        user_preferences={"profile": {"alerts": "Never", "emails": "Daily"}},
        with_audit_firm=True,
        audit_firm=graphql_audit_firm.name,
    )


@pytest.fixture
def audit_from_organization_b(
    different_organization, graphql_audit_user, graphql_audit_firm
):
    in_progress = create_audit(
        organization=different_organization,
        name='Audit from different organization',
        audit_firm=graphql_audit_firm,
    )

    AuditStatus.objects.create(audit=in_progress, initiated=True)
    AuditAuditor.objects.create(audit=in_progress, auditor=graphql_audit_user.auditor)


@pytest.fixture
def in_progress_audit(
    graphql_organization,
    graphql_audit_user,
    graphql_audit_firm,
    soc2_type1_coupon,
    soc2_type1_audit_framework_type,
):
    in_progress = create_audit(
        organization=graphql_organization,
        name=AUDIT_NAME,
        audit_firm=graphql_audit_firm,
    )

    fieldwork = create_audit(
        organization=graphql_organization,
        name=AUDIT_NAME,
        audit_firm=graphql_audit_firm,
        is_completed=True,
    )

    completed = create_audit(
        organization=graphql_organization,
        name=AUDIT_NAME,
        audit_firm=graphql_audit_firm,
        is_completed=True,
    )

    second_completed = create_audit(
        organization=graphql_organization,
        name='Test Completed Second',
        audit_firm=graphql_audit_firm,
        is_completed=True,
    )

    second_in_progress = create_audit(
        organization=graphql_organization,
        name='Test In Progress Second',
        audit_firm=graphql_audit_firm,
        is_completed=True,
    )

    second_in_progress.created_at = datetime.now() - timedelta(days=2)
    second_in_progress.save()
    AuditStatus.objects.create(audit=in_progress, initiated=True)
    AuditStatus.objects.create(audit=fieldwork, fieldwork=True)
    AuditStatus.objects.create(audit=completed, completed=True)
    AuditStatus.objects.create(audit=second_completed, completed=True)
    AuditStatus.objects.create(audit=second_in_progress, initiated=True)

    AuditAuditor.objects.create(audit=in_progress, auditor=graphql_audit_user.auditor)
    AuditAuditor.objects.create(audit=fieldwork, auditor=graphql_audit_user.auditor)
    AuditAuditor.objects.create(audit=completed, auditor=graphql_audit_user.auditor)
    AuditAuditor.objects.create(
        audit=second_completed, auditor=graphql_audit_user.auditor
    )
    AuditAuditor.objects.create(
        audit=second_in_progress, auditor=graphql_audit_user.auditor
    )


@pytest.fixture
def past_audit(graphql_organization, graphql_audit_firm):
    audit = create_audit(
        organization=graphql_organization,
        name=AUDIT_NAME,
        audit_firm=graphql_audit_firm,
        is_completed=True,
    )

    AuditStatus.objects.create(audit=audit, initiated=True)
    AuditStatus.objects.create(audit=audit, requested=True)
    AuditStatus.objects.create(audit=audit, fieldwork=True)
    AuditStatus.objects.create(audit=audit, in_draft_report=True)
    AuditStatus.objects.create(audit=audit, completed=True)
    return audit


@pytest.fixture
def audit_status_past_audit(past_audit):
    return create_audit_status(audit=past_audit)


@pytest.fixture
def audit_in_progress(graphql_organization, graphql_audit_firm, soc2_type1_coupon):
    audit_1 = create_audit(
        organization=graphql_organization,
        name=AUDIT_NAME,
        audit_firm=graphql_audit_firm,
    )
    audit_2 = create_audit(
        organization=graphql_organization,
        name=AUDIT_NAME,
        audit_firm=graphql_audit_firm,
    )

    AuditStatus.objects.create(audit=audit_1, requested=True)
    AuditStatus.objects.create(audit=audit_2, requested=True, initiated=True)


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_audit_types(
    graphql_client,
    organization_audit_firm,
    soc2_type1_audit_framework_type,
    soc2_type2_audit_framework_type,
):
    response = graphql_client.execute(GET_AUDIT_TYPES)
    audit_types = response['data']['auditTypes']
    assert len(audit_types) == 2


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_audit_types_no_unlocked_framework(
    graphql_client, organization_audit_firm, hitrust_audit_framework_type
):
    response = graphql_client.execute(GET_AUDIT_TYPES)
    audit_types = response['data']['auditTypes']
    assert len(audit_types) == 0


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_past_audits(graphql_organization, graphql_client, past_audit):
    response = graphql_client.execute(GET_PAST_AUDITS)
    past_audits = response['data']['pastAudits']
    assert len(past_audits) == 1


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_auditor_past_audits(
    graphql_audit_client, graphql_audit_user, past_audit, audit_status_past_audit
):
    AuditAuditor.objects.create(audit=past_audit, auditor=graphql_audit_user.auditor)

    response = graphql_audit_client.execute(GET_AUDITOR_PAST_AUDITS)
    auditor_past_audits = response['data']['auditorPastAudits']
    assert len(auditor_past_audits) > 0


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_auditor_past_audits_sorted_by_completed_at(
    graphql_audit_client, in_progress_audit, soc2_type1_coupon
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_PAST_AUDITS,
        variables={'orderBy': {'field': 'completed_at', 'order': 'descend'}},
    )

    auditor_past_audits = response['data']['auditorPastAudits']['audits']
    assert len(auditor_past_audits) == 2
    assert auditor_past_audits[0].get("name") == "Test Completed Second"


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_auditor_past_audits_default_sorting(
    graphql_audit_client,
    in_progress_audit,
    soc2_type1_coupon,
    completed_audit_soc2_type2,
):
    response = graphql_audit_client.execute(GET_AUDITOR_PAST_AUDITS)
    auditor_past_audits = response['data']['auditorPastAudits']['audits']

    assert len(auditor_past_audits) == 3
    assert auditor_past_audits[0]['auditType'].get('type') == SOC_2_TYPE_1_NAME
    assert auditor_past_audits[1]['auditType'].get('type') == SOC_2_TYPE_1_NAME
    assert auditor_past_audits[2]['auditType'].get('type') == SOC_2_TYPE_2_NAME


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_auditor_past_audits_filtered_by_name(
    graphql_audit_client, in_progress_audit, soc2_type1_coupon
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_PAST_AUDITS,
        variables={'searchCriteria': 'Second'},
    )

    auditor_past_audits = response['data']['auditorPastAudits']['audits']
    assert len(auditor_past_audits) == 1
    assert auditor_past_audits[0].get("name") == "Test Completed Second"


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_audits_in_progress(
    graphql_organization,
    graphql_client,
    audit_in_progress,
    soc2_type1_coupon,
    soc2_type1_audit_framework_type,
):
    audit_type_id_1 = 'SOC 2 Type 1_Test Audit Firm_1'
    audit_type_id_2 = 'SOC 2 Type 1_Test Audit Firm_2'
    requested = CURRENT_AUDIT_STATUS['REQUESTED']
    initiated = CURRENT_AUDIT_STATUS['INITIATED']

    response = graphql_client.execute(GET_AUDITS_IN_PROGRESS)
    audits_in_progress = response['data']['auditsInProgress']
    audit_type_1 = audits_in_progress[0]['auditType']
    audit_type_2 = audits_in_progress[1]['auditType']
    audit_status_1 = audits_in_progress[0]['status']
    audit_status_2 = audits_in_progress[1]['status']

    assert len(audits_in_progress) == 2
    assert audit_type_1['id'] == audit_type_id_1
    assert audit_type_2['id'] == audit_type_id_2
    assert audit_status_1['currentStatus'] == requested
    assert audit_status_2['currentStatus'] == initiated


@pytest.mark.functional(permissions=['audit.add_audit'])
def test_create_audit_no_coupons(
    graphql_client,
    organization_audit_firm,
    soc2_type1_audit_framework_type,
    soc2_type1_no_coupons,
    graphql_audit_firm,
):
    add_audit_input = {
        'input': dict(
            name='Laika Dev Soc 2 Type 1 fail Audit 2021',
            auditType=AUDIT_TYPES[0],
            auditConfiguration='{"trusted_services_categories": ["Security"]}',
            auditFirmName=graphql_audit_firm.name,
        )
    }

    response = graphql_client.execute(CREATE_AUDIT, variables=add_audit_input)

    audit_count = Audit.objects.all().count()
    assert audit_count == 0
    assert response['errors'][0].get('message') == 'No coupons available'


@patch(
    'audit.sections_factory.SOC2_Type1_sections_factory.build_criteria_table',
    return_value=CRITERIA_MOCK_DATA,
)
@patch(
    'audit.sections_factory.utils.get_requirements_by_args',
    return_value=Requirement.objects.all(),
)
@pytest.mark.functional(permissions=['audit.add_audit'])
def test_create_audit(
    get_requirements_by_args_mock,
    build_criteria_table_mock,
    graphql_client,
    soc2_type1_coupon,
    organization_audit_firm,
    soc2_type1_audit_framework_type,
    graphql_audit_firm,
):
    AuditorFlag.objects.create(
        name='draftReportV2FeatureFlag',
        audit_firm=graphql_audit_firm,
    )
    add_audit_input = {
        'input': dict(
            name=AUDIT_NAME,
            auditType=AUDIT_TYPES[0],
            auditConfiguration=AUDIT_CONFIGURATION,
            auditFirmName=graphql_audit_firm.name,
        )
    }

    graphql_client.execute(CREATE_AUDIT, variables=add_audit_input)

    audits = Audit.objects.all()
    assert audits.count() == 1
    audit = audits.first()
    assert audit.name == AUDIT_NAME
    assert audit.status.first().requested is True
    assert build_criteria_table_mock.call_count == 2
    assert get_requirements_by_args_mock.call_count == 1


@pytest.mark.functional(permissions=['audit.add_audit'])
def test_create_audit_invalid_audit_type(
    graphql_client,
    organization_audit_firm,
    graphql_audit_firm,
    soc2_type1_audit_framework_type,
):
    add_audit_input = {
        'input': dict(
            name=AUDIT_NAME,
            auditType='Test',
            auditConfiguration=AUDIT_CONFIGURATION,
            auditFirmName=graphql_audit_firm.name,
        )
    }

    executed = graphql_client.execute(CREATE_AUDIT, variables=add_audit_input)
    response = executed['errors']
    assert len(response) == 1
    assert response[0]['message'] == 'Audit type not supported!'


@pytest.mark.functional(permissions=['audit.view_audit', 'audit.add_audit'])
@patch('audit.types.DocuSignConnection.get_envelope_status', return_value='sent')
@patch('audit.types.get_email_domain_from_users', return_value='@heylaika.com')
def test_get_audit(
    get_email_domain_from_users_mock,
    get_envelope_status_mock,
    audit,
    graphql_client,
    organization_audit_firm,
    audit_status,
    laika_super_admin,
):
    first_name = laika_super_admin.first_name
    last_name = laika_super_admin.last_name
    approver = f'{first_name} {last_name}'

    response = graphql_client.execute(GET_AUDIT, variables={'id': '1'})
    response_audit = response['data']['audit']
    assert response_audit['auditType']['type'] == 'SOC 2 Type 1'
    assert response_audit['status']['draftReportApproverName'] == approver


# TODO: Remove skip or remove the test as part of
#  https://heylaika.atlassian.net/browse/FZ-1736
@pytest.mark.skip('Query does not make sense')
@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_auditor_audit(graphql_client, audit, graphql_user, graphql_audit_user):
    auditor = Auditor(user=graphql_user)
    auditor.save(is_not_django=True)
    auditor.user.role = 'Auditor'
    auditor.user.save()

    response = graphql_client.execute(
        GET_AUDITOR_AUDIT,
        variables={'id': '1'},
    )
    assert response['data']['auditorAudit'] is None

    AuditAuditor.objects.create(audit=audit, auditor=auditor)
    response = graphql_client.execute(
        GET_AUDITOR_AUDIT,
        variables={'id': '1'},
    )
    assert response['data']['auditorAudit']['id'] == '1'


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_check_audit_status_field(
    graphql_client, audit, graphql_audit_user, graphql_user
):
    audit_status = create_audit_status(audit=audit)

    audit_status.requested = True
    audit_status.initiated = True
    audit_status.control_design_assessment_checked = True
    audit_status.kickoff_meeting_checked = True
    audit_status.engagement_letter_checked = False
    audit_status.save()

    alert = audit_status.create_auditor_alert(
        sender=graphql_user,
        receiver=graphql_audit_user.auditor.user,
        alert_type=ALERT_TYPES['ORG_COMPLETED_INITIATION'],
    )

    alert.send_auditor_alert_email(audit_status=audit_status)

    id = audit_status.id
    input = {
        'input': dict(statusId=id, field='engagement_letter_checked', auditId=audit.id)
    }

    graphql_client.execute(CHECK_AUDIT_STATUS_FIELD, variables=input)
    updated_audit_status = AuditStatus.objects.get(id=id)
    assert updated_audit_status.engagement_letter_checked is True

    audit_status.fieldwork = True
    audit_status.in_draft_report = True
    audit_status.review_draft_report_checked = True
    audit_status.representation_letter_checked = True
    audit_status.management_assertion_checked = True
    audit_status.subsequent_events_questionnaire_checked = False
    audit_status.save()

    draft_report_input = {
        'input': dict(
            statusId=id,
            field='subsequent_events_questionnaire_checked',
            auditId=audit.id,
        )
    }
    graphql_client.execute(CHECK_AUDIT_STATUS_FIELD, variables=draft_report_input)

    updated_audit_status = AuditStatus.objects.get(id=id)
    assert updated_audit_status.subsequent_events_questionnaire_checked is True


@pytest.mark.functional(permissions=['alert.add_alert'])
def test_create_audit_alert(past_audit, laika_super_admin):
    audit_status = AuditStatus.objects.create(audit=past_audit, requested=True)

    audit_status.initiated = True
    audit_status.save()
    audit_status.create_audit_stage_alerts()

    audit_alerts = AuditAlert.objects.all()
    assert len(audit_alerts) > 0


# Auditor functional tests
# TODO: we should refactor the queries for the list of audits,
# https://heylaika.atlassian.net/browse/FZ-1848


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_all_ongoing_audits(graphql_audit_client, in_progress_audit):
    response = graphql_audit_client.execute(GET_ALL_ONGOING_AUDITS)
    all_ongoing_audits = response['data']['allOngoingAudits']['audits']
    assert len(all_ongoing_audits) == 3


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_all_ongoing_audits_filtered_by_name(graphql_audit_client, in_progress_audit):
    response = graphql_audit_client.execute(
        GET_ALL_ONGOING_AUDITS, variables={'searchCriteria': 'Second'}
    )
    all_ongoing_audits = response['data']['allOngoingAudits']['audits']
    assert len(all_ongoing_audits) == 1
    assert all_ongoing_audits[0].get("name") == "Test In Progress Second"


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_all_ongoing_audits_sorted_by_organization(
    graphql_audit_client, in_progress_audit, audit_from_organization_b
):
    response = graphql_audit_client.execute(
        GET_ALL_ONGOING_AUDITS,
        variables={
            'orderBy': {'field': 'organization__name', 'order': 'ascend'},
        },
    )
    all_ongoing_audits = response['data']['allOngoingAudits']['audits']
    assert len(all_ongoing_audits) == 4
    assert all_ongoing_audits[3].get("name") == "Audit from different organization"


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_all_ongoing_audits_sorted_by_name(graphql_audit_client, in_progress_audit):
    response = graphql_audit_client.execute(
        GET_ALL_ONGOING_AUDITS,
        variables={
            'orderBy': {'field': 'audit_type', 'order': 'descend'},
        },
    )
    all_ongoing_audits = response['data']['allOngoingAudits']['audits']
    assert len(all_ongoing_audits) == 3
    assert all_ongoing_audits[2].get("name") == "Test In Progress Second"


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_all_ongoing_audits_sorted_by_status_asc(
    graphql_audit_client, in_progress_audit
):
    response = graphql_audit_client.execute(
        GET_ALL_ONGOING_AUDITS,
        variables={
            'orderBy': {'field': 'stage', 'order': 'ascend'},
        },
    )
    all_ongoing_audits = response['data']['allOngoingAudits']['audits']
    assert len(all_ongoing_audits) == 3
    assert (
        all_ongoing_audits[0].get("status")['currentStatus']
        == CURRENT_AUDIT_STATUS['FIELDWORK']
    )
    assert (
        all_ongoing_audits[1]['status'].get('currentStatus')
        == CURRENT_AUDIT_STATUS['INITIATED']
    )
    assert (
        all_ongoing_audits[2]['status']['currentStatus']
        == CURRENT_AUDIT_STATUS['INITIATED']
    )


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_all_ongoing_audits_sorted_by_status_desc(
    graphql_audit_client, in_progress_audit
):
    response = graphql_audit_client.execute(
        GET_ALL_ONGOING_AUDITS,
        variables={
            'orderBy': {'field': 'stage', 'order': 'descend'},
        },
    )
    all_ongoing_audits = response['data']['allOngoingAudits']['audits']
    assert len(all_ongoing_audits) == 3
    assert (
        all_ongoing_audits[0]['status'].get('currentStatus')
        == CURRENT_AUDIT_STATUS['INITIATED']
    )
    assert (
        all_ongoing_audits[1]['status']['currentStatus']
        == CURRENT_AUDIT_STATUS['INITIATED']
    )
    assert (
        all_ongoing_audits[2].get("status")['currentStatus']
        == CURRENT_AUDIT_STATUS['FIELDWORK']
    )


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_all_ongoing_audits_default_sorting(
    graphql_audit_client,
    in_progress_audit,
    requested_audit_soc2_type2,
    fieldwork_audit_soc2_type2,
    in_draft_report_audit_soc2_type2,
):
    response = graphql_audit_client.execute(
        GET_ALL_ONGOING_AUDITS,
    )
    all_ongoing_audits = response['data']['allOngoingAudits']['audits']

    assert len(all_ongoing_audits) == 6
    assert (
        all_ongoing_audits[0]['status'].get('currentStatus')
        == CURRENT_AUDIT_STATUS['IN_DRAFT_REPORT']
    )
    assert all_ongoing_audits[0]['auditType'].get('type') == SOC_2_TYPE_2_NAME

    assert (
        all_ongoing_audits[1]['status'].get('currentStatus')
        == CURRENT_AUDIT_STATUS['FIELDWORK']
    )
    assert all_ongoing_audits[1]['auditType'].get('type') == SOC_2_TYPE_1_NAME

    assert (
        all_ongoing_audits[2]['status'].get('currentStatus')
        == CURRENT_AUDIT_STATUS['FIELDWORK']
    )
    assert all_ongoing_audits[2]['auditType'].get('type') == SOC_2_TYPE_2_NAME

    assert (
        all_ongoing_audits[3]['status'].get('currentStatus')
        == CURRENT_AUDIT_STATUS['INITIATED']
    )
    assert all_ongoing_audits[3]['auditType'].get('type') == SOC_2_TYPE_1_NAME

    assert (
        all_ongoing_audits[4]['status'].get('currentStatus')
        == CURRENT_AUDIT_STATUS['INITIATED']
    )
    assert all_ongoing_audits[4]['auditType'].get('type') == SOC_2_TYPE_1_NAME

    assert (
        all_ongoing_audits[5]['status'].get('currentStatus')
        == CURRENT_AUDIT_STATUS['INITIATED']
    )
    assert all_ongoing_audits[5]['auditType'].get('type') == SOC_2_TYPE_2_NAME


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_auditor_ongoing_audits(graphql_audit_client, in_progress_audit):
    response = graphql_audit_client.execute(GET_AUDITOR_ONGOING_AUDITS)
    auditor_ongoing_audits = response['data']['auditorOngoingAudits']['audits']
    assert len(auditor_ongoing_audits) == 3


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_auditor_ongoing_audits_default_sorting(
    graphql_audit_client,
    in_progress_audit,
    requested_audit_soc2_type2,
    in_draft_report_audit_soc2_type2,
):
    response = graphql_audit_client.execute(GET_AUDITOR_ONGOING_AUDITS)
    auditor_ongoing_audits = response['data']['auditorOngoingAudits']['audits']
    assert (
        auditor_ongoing_audits[0]['status'].get('currentStatus')
        == CURRENT_AUDIT_STATUS['IN_DRAFT_REPORT']
    )
    assert auditor_ongoing_audits[0]['auditType'].get('type') == SOC_2_TYPE_2_NAME

    assert (
        auditor_ongoing_audits[1]['status'].get('currentStatus')
        == CURRENT_AUDIT_STATUS['FIELDWORK']
    )
    assert auditor_ongoing_audits[1]['auditType'].get('type') == SOC_2_TYPE_1_NAME

    assert (
        auditor_ongoing_audits[2]['status'].get('currentStatus')
        == CURRENT_AUDIT_STATUS['INITIATED']
    )
    assert auditor_ongoing_audits[2]['auditType'].get('type') == SOC_2_TYPE_1_NAME

    assert (
        auditor_ongoing_audits[3]['status'].get('currentStatus')
        == CURRENT_AUDIT_STATUS['INITIATED']
    )
    assert auditor_ongoing_audits[3]['auditType'].get('type') == SOC_2_TYPE_1_NAME

    assert (
        auditor_ongoing_audits[4]['status'].get('currentStatus')
        == CURRENT_AUDIT_STATUS['INITIATED']
    )
    assert auditor_ongoing_audits[4]['auditType'].get('type') == SOC_2_TYPE_2_NAME


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_auditor_ongoing_audits_filtered_by_name(
    graphql_audit_client, in_progress_audit
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_ONGOING_AUDITS, variables={'searchCriteria': 'Second'}
    )
    auditor_ongoing_audits = response['data']['auditorOngoingAudits']['audits']
    assert len(auditor_ongoing_audits) == 1
    assert auditor_ongoing_audits[0].get("name") == "Test In Progress Second"


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_auditor_ongoing_audits_sorted_by_name(graphql_audit_client, in_progress_audit):
    response = graphql_audit_client.execute(
        GET_AUDITOR_ONGOING_AUDITS,
        variables={
            'orderBy': {'field': 'name', 'order': 'ascend'},
        },
    )
    auditor_ongoing_audits = response['data']['auditorOngoingAudits']['audits']
    assert len(auditor_ongoing_audits) == 3
    assert auditor_ongoing_audits[2].get("name") == "Test In Progress Second"


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_auditor_ongoing_audits_sorted_by_status_asc(
    graphql_audit_client, in_progress_audit
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_ONGOING_AUDITS,
        variables={
            'orderBy': {'field': 'stage', 'order': 'ascend'},
        },
    )
    auditor_ongoing_audits = response['data']['auditorOngoingAudits']['audits']
    assert len(auditor_ongoing_audits) == 3
    assert (
        auditor_ongoing_audits[0].get("status")['currentStatus']
        == CURRENT_AUDIT_STATUS['FIELDWORK']
    )
    assert (
        auditor_ongoing_audits[1]['status'].get('currentStatus')
        == CURRENT_AUDIT_STATUS['INITIATED']
    )
    assert (
        auditor_ongoing_audits[2]['status']['currentStatus']
        == CURRENT_AUDIT_STATUS['INITIATED']
    )


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_auditor_ongoing_audits_sorted_by_status_desc(
    graphql_audit_client, in_progress_audit
):
    response = graphql_audit_client.execute(
        GET_AUDITOR_ONGOING_AUDITS,
        variables={
            'orderBy': {'field': 'stage', 'order': 'descend'},
        },
    )
    auditor_ongoing_audits = response['data']['auditorOngoingAudits']['audits']
    assert len(auditor_ongoing_audits) == 3
    assert (
        auditor_ongoing_audits[0]['status'].get('currentStatus')
        == CURRENT_AUDIT_STATUS['INITIATED']
    )
    assert (
        auditor_ongoing_audits[1]['status']['currentStatus']
        == CURRENT_AUDIT_STATUS['INITIATED']
    )
    assert (
        auditor_ongoing_audits[2].get("status")['currentStatus']
        == CURRENT_AUDIT_STATUS['FIELDWORK']
    )


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_update_audit_stage_error(graphql_client, audit):
    args = {'requested': True}
    audit_status = create_audit_status(audit=audit, **args)
    enable_stage = CURRENT_AUDIT_STATUS['INITIATED']

    response = graphql_client.execute(
        UPDATE_AUDIT_STAGE,
        variables={'input': dict(id=audit_status.id, enableStage=enable_stage)},
    )

    assert response['errors'][0]['message'] == 'Failed to move audit to next stage.'


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_update_audit_stage(graphql_client, audit):
    args = {
        'requested': True,
        'confirm_audit_details': True,
        'engagement_letter_link': 'YYY',
        'control_design_assessment_link': 'YYY',
        'kickoff_meeting_link': 'YYY',
        'confirm_engagement_letter_signed': True,
        'confirm_control_design_assessment': True,
        'confirm_kickoff_meeting': True,
        'representation_letter_link': 'YYY',
        'management_assertion_link': 'YYY',
        'subsequent_events_questionnaire_link': 'YYY',
        'draft_report': 'YYY',
        'confirm_completion_of_signed_documents': True,
        'final_report': 'YYY',
    }
    audit_status = create_audit_status(audit=audit, **args)

    for stage in CURRENT_AUDIT_STATUS.keys():
        graphql_client.execute(
            UPDATE_AUDIT_STAGE,
            variables={'input': dict(id=audit_status.id, enableStage=stage)},
        )
        status = AuditStatus.objects.get(pk=audit_status.id)
        assert getattr(status, stage.lower())


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_update_audit_stage_initiated(graphql_audit_client, audit_status):
    initiated = CURRENT_AUDIT_STATUS['INITIATED']
    graphql_audit_client.execute(
        AUDITOR_UPDATE_AUDIT_STAGE,
        variables={'input': dict(id=audit_status.id, enableStage=initiated)},
    )
    status = AuditStatus.objects.get(id=audit_status.id)
    today = datetime.now().strftime("%Y/%m/%d")

    assert status.initiated
    assert status.initiated_created_at.strftime("%Y/%m/%d") == today
    assert not status.fieldwork_created_at
    assert not status.in_draft_report_created_at
    assert not status.audit.completed_at


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_update_audit_stage_fieldwork(graphql_audit_client, audit_status):
    args = {'initiated': True, 'initiated_created_at': '2022-06-01'}
    AuditStatus.objects.filter(id=audit_status.id).update(**args)
    audit_status = AuditStatus.objects.get(id=audit_status.id)

    graphql_audit_client.execute(
        AUDITOR_UPDATE_AUDIT_STAGE,
        variables={
            'input': dict(
                id=audit_status.id, enableStage=CURRENT_AUDIT_STATUS['FIELDWORK']
            )
        },
    )
    status = AuditStatus.objects.get(id=audit_status.id)
    today = datetime.now().strftime("%Y/%m/%d")

    assert status.initiated_created_at == audit_status.initiated_created_at
    assert status.fieldwork
    assert status.fieldwork_created_at.strftime("%Y/%m/%d") == today
    assert not status.in_draft_report_created_at
    assert not status.audit.completed_at


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_update_audit_stage_in_draft_report(graphql_audit_client, audit_status):
    args = {
        'initiated': True,
        'initiated_created_at': '2022-06-01',
        'fieldwork': True,
        'fieldwork_created_at': '2022-06-02',
    }
    AuditStatus.objects.filter(id=audit_status.id).update(**args)
    audit_status = AuditStatus.objects.get(id=audit_status.id)

    graphql_audit_client.execute(
        AUDITOR_UPDATE_AUDIT_STAGE,
        variables={'input': dict(id=audit_status.id, enableStage='in_draft_report')},
    )
    status = AuditStatus.objects.get(id=audit_status.id)
    today = datetime.now().strftime("%Y/%m/%d")

    assert status.initiated_created_at == audit_status.initiated_created_at
    assert status.fieldwork_created_at == audit_status.fieldwork_created_at
    assert status.in_draft_report
    assert status.in_draft_report_created_at.strftime("%Y/%m/%d") == today
    assert not status.audit.completed_at


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_update_audit_stage_completed(graphql_audit_client, audit_status):
    args = {
        'initiated': True,
        'initiated_created_at': '2022-06-01',
        'fieldwork': True,
        'fieldwork_created_at': '2022-06-02',
        'in_draft_report': True,
        'in_draft_report_created_at': '2022-06-03',
    }
    AuditStatus.objects.filter(id=audit_status.id).update(**args)
    audit_status = AuditStatus.objects.get(id=audit_status.id)

    graphql_audit_client.execute(
        AUDITOR_UPDATE_AUDIT_STAGE,
        variables={
            'input': dict(
                id=audit_status.id, enableStage=CURRENT_AUDIT_STATUS['COMPLETED']
            )
        },
    )
    status = AuditStatus.objects.get(id=audit_status.id)
    today = datetime.now().strftime("%Y/%m/%d")

    assert status.initiated_created_at == audit_status.initiated_created_at
    assert status.fieldwork_created_at == audit_status.fieldwork_created_at
    assert status.in_draft_report_created_at == audit_status.in_draft_report_created_at
    assert status.completed
    assert status.audit.completed_at.strftime("%Y/%m/%d") == today


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_audit_team(
    graphql_audit_client, audit, auditor_with_firm, auditor_with_firm_2
):
    d = dict(TITLE_ROLES)
    AuditAuditor.objects.create(
        audit=audit, auditor=auditor_with_firm, title_role=LEAD_AUDITOR
    )
    AuditAuditor.objects.create(
        audit=audit, auditor=auditor_with_firm_2, title_role=d['tester']
    )
    response = graphql_audit_client.execute(
        GET_AUDIT_TEAM, variables={'id': str(audit.id)}
    )

    audit_team = response['data']['auditTeam']['auditors']
    assert len(audit_team) == 2
    assert audit_team[0]['user']['email'] == 'matt@heylaika.com'
    assert audit_team[0]['auditInProgress'] == 1
    assert audit_team[1]['user']['email'] == 'annie@heylaika.com'
    assert audit_team[1]['auditInProgress'] == 1


@pytest.mark.functional(permissions=['audit.assign_audit'])
def test_assign_audit_to_auditor(graphql_audit_client, audit, graphql_audit_user):
    role = LEAD_AUDITOR
    response = graphql_audit_client.execute(
        ASSIGN_AUDIT_TO_AUDITOR,
        variables={
            'input': dict(
                auditId=audit.id, auditorEmails=[graphql_audit_user.email], role=role
            )
        },
    )
    audit_id = response['data']['assignAuditToAuditor']['auditId']
    assert audit_id == str(audit.id)


@pytest.mark.functional(permissions=['audit.assign_audit'])
def test_assign_audit_to_auditor_error(graphql_audit_client, audit, auditor, auditor2):
    role = LEAD_AUDITOR
    graphql_audit_client.execute(
        ASSIGN_AUDIT_TO_AUDITOR,
        variables={
            'input': dict(
                auditId=audit.id, auditorEmails=[auditor.user.email], role=role
            )
        },
    )
    response = graphql_audit_client.execute(
        ASSIGN_AUDIT_TO_AUDITOR,
        variables={
            'input': dict(
                auditId=audit.id, auditorEmails=[auditor2.user.email], role=role
            )
        },
    )
    assert (
        response['errors'][0]['message']
        == 'Lead Auditor role already exist in the team. Please select another role.'
    )


@pytest.mark.functional(permissions=['audit.assign_audit'])
def test_remove_auditor_from_audit(
    graphql_audit_client, audit, auditor_with_firm, auditor_with_firm_2
):
    d = dict(TITLE_ROLES)
    AuditAuditor.objects.create(
        audit=audit, auditor=auditor_with_firm, title_role=d['lead_auditor']
    )
    AuditAuditor.objects.create(
        audit=audit, auditor=auditor_with_firm_2, title_role=d['tester']
    )
    response = graphql_audit_client.execute(
        REMOVE_AUDITOR_FROM_AUDIT,
        variables={
            'input': dict(auditId=audit.id, auditorEmail=auditor_with_firm.user.email)
        },
    )
    audit_id = response['data']['removeAuditorFromAudit']['auditId']
    assert audit_id == str(audit.id)


@pytest.mark.functional(permissions=['audit.assign_audit'])
def test_remove_auditor_from_audit_error(graphql_audit_client, audit, auditor):
    d = dict(TITLE_ROLES)
    AuditAuditor.objects.create(
        audit=audit, auditor=auditor, title_role=d['lead_auditor']
    )
    response = graphql_audit_client.execute(
        REMOVE_AUDITOR_FROM_AUDIT,
        variables={'input': dict(auditId=audit.id, auditorEmail=auditor.user.email)},
    )
    audit_id = response['data']['removeAuditorFromAudit']['auditId']
    assert audit_id == str(audit.id)


@pytest.mark.functional(permissions=['audit.delete_audit_user'])
def test_delete_auditor_users(graphql_client):
    email = 'test-del@heylaika.com'
    create_user_auditor(
        email=email,
        role=AUDITOR_ADMIN,
        first_name='Ivo',
        last_name='Test',
        user_preferences={"profile": {"alerts": "Never", "emails": "Daily"}},
    )
    assert Auditor.objects.all().first().user.first_name == 'Ivo'

    response = graphql_client.execute(DELETE_AUDITOR_USERS, variables={'input': email})
    response['data']['deleteAuditUsers']
    auditor_exists = Auditor.objects.filter(user__email__in=email).exists()

    assert auditor_exists is False


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_auditors(
    graphql_audit_client,
    auditor,
    auditor2,
    auditor_with_firm,
    auditor_with_firm_2,
    organization_audit_firm,
    graphql_audit_firm,
):
    response = graphql_audit_client.execute(GET_AUDITORS)
    auditors = response['data']['auditors']

    assert len(auditors) == 2


@pytest.mark.functional(permissions=['audit.view_audit_firm_auditors'])
def test_get_auditor_users(graphql_audit_client, auditor, auditor2, auditor_with_firm):
    response = graphql_audit_client.execute(GET_AUDITOR_USERS)
    auditors = response['data']['auditorUsers']

    assert len(auditors) == 2


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_auditor_user(graphql_audit_client, auditor):
    response = graphql_audit_client.execute(GET_AUDITOR_USER)
    assert response['data']['auditorUser'] is not None


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_generate_report_datetime(graphql_audit_client, audit):
    audit_status = AuditStatus.objects.create(
        audit=audit, requested=True, fieldwork=True, in_draft_report=True
    )

    graphql_audit_client.execute(
        AUDITOR_UPDATE_AUDIT_CONTENT_STEP,
        variables={
            'input': dict(
                auditId=audit.id,
                statusId=audit_status.id,
                field='draft_report_generated',
                value=True,
            )
        },
    )
    audit_status = AuditStatus.objects.get(id=audit_status.id)

    first_draft_report_generated_timestamp = (
        audit_status.first_draft_report_generated_timestamp
    )

    graphql_audit_client.execute(
        AUDITOR_UPDATE_AUDIT_CONTENT_STEP,
        variables={
            'input': dict(
                auditId=audit.id,
                statusId=audit_status.id,
                field='draft_report_generated',
                value=True,
            )
        },
    )

    updated_status = AuditStatus.objects.get(id=audit_status.id)
    assert (
        first_draft_report_generated_timestamp
        == updated_status.first_draft_report_generated_timestamp
    )


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_checked_report_datetime(graphql_audit_client, audit):
    audit_status = AuditStatus.objects.create(
        audit=audit, requested=True, fieldwork=True, in_draft_report=True
    )
    graphql_audit_client.execute(
        CHECK_AUDIT_STATUS_FIELD,
        variables={
            'input': dict(
                auditId=audit.id,
                statusId=audit_status.id,
                field='review_draft_report_checked',
            )
        },
    )

    audit_accepted_status = AuditStatus.objects.get(id=audit_status.id)
    assert audit_accepted_status.draft_report_checked_timestamp is not None


@pytest.mark.functional(permissions=['audit.change_audit_user'])
@pytest.mark.skipif(
    True,
    reason='''We can not test this because it tries
                                    to edit in cognito a user that will
                                    not exist because only exists in the
                                    test''',
)
def test_update_auditor(graphql_client):
    email = 'test-update@heylaika.com'
    create_user_auditor(
        email=email,
        username=email,
        role=AUDITOR_ADMIN,
        first_name='Test',
        last_name='Auditor',
    )

    graphql_client.execute(
        UPDATE_AUDITOR,
        variables={
            'input': dict(
                firstName='User', lastName='Updated', email=email, role=AUDITOR_ADMIN
            )
        },
    )

    auditor_user = User.objects.get(email=email)

    assert auditor_user.first_name == 'User'
    assert auditor_user.last_name == 'Updated'


@pytest.mark.functional(permissions=['audit.change_audit_user'])
@pytest.mark.skipif(
    True,
    reason='''We can not test this because it tries
                                    to edit in cognito a user that will
                                    not exist because only exists in the
                                    test''',
)
def test_update_auditor_permission(graphql_client):
    email = 'test-update@heylaika.com'
    create_user_auditor(
        email=email,
        username=email,
        role=AUDITOR_ADMIN,
        first_name='Test',
        last_name='Auditor',
    )

    graphql_client.execute(
        UPDATE_AUDITOR,
        variables={
            'input': dict(
                firstName='Test', lastName='Auditor', email=email, role=AUDITOR
            )
        },
    )

    auditor_user = User.objects.get(email=email)

    assert auditor_user.role == AUDITOR


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_generate_upload_draft_report_datetime(graphql_audit_client, audit):
    audit_status = AuditStatus.objects.create(
        audit=audit, requested=True, fieldwork=True, in_draft_report=True
    )

    graphql_audit_client.execute(
        AUDITOR_UPDATE_AUDIT_CONTENT_STEP,
        variables={
            'input': dict(
                auditId=audit.id,
                statusId=audit_status.id,
                field='draft_report',
                value='Test',
                fileName='test',
            )
        },
    )

    audit_step_timestamp_count = AuditStepTimestamp.objects.count()
    assert audit_step_timestamp_count == 1


@pytest.mark.functional(permissions=['audit.change_audit'])
def test_update_auditor_audit(graphql_audit_client, audit):
    name_to_update = "frozen test type 2"
    configuration_to_update = {
        "as_of_date": "2021-05-25",
        "trust_services_categories": ["Availability", "Process Integrity"],
    }
    configuration_to_update_string = json.dumps(configuration_to_update)

    legal_name = 'Laika Dev Legal Name'
    short_name = 'Laika Dev'
    system_name = 'My system Name'

    response = graphql_audit_client.execute(
        AUDITOR_UPDATE_AUDIT_DETAILS,
        variables={
            'input': dict(
                auditId=audit.id,
                name=name_to_update,
                auditConfiguration=configuration_to_update_string,
                legalName=legal_name,
                shortName=short_name,
                systemName=system_name,
            )
        },
    )

    updated_audit = response['data']['updateAuditorAuditDetails']['updated']
    audit_configuration_dict = json.loads(updated_audit['auditConfiguration'])
    updated_audit_as_of_date = audit_configuration_dict["as_of_date"]
    updated_audit_trust_services_categories = audit_configuration_dict[
        "trust_services_categories"
    ]

    assert updated_audit["name"] == name_to_update
    assert updated_audit_as_of_date == configuration_to_update["as_of_date"]
    assert (
        updated_audit_trust_services_categories
        == configuration_to_update["trust_services_categories"]
    )

    organization = updated_audit["auditOrganization"]
    assert organization['legalName'] == legal_name
    assert organization['name'] == short_name
    assert organization['systemName'] == system_name


@pytest.mark.functional(permissions=['audit.assign_audit'])
def test_update_auditor_role_in_audit_team(
    graphql_audit_client, audit, auditor, auditor2
):
    AuditAuditor.objects.create(audit=audit, auditor=auditor, title_role='lead_auditor')
    AuditAuditor.objects.create(audit=audit, auditor=auditor2, title_role='tester')

    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_ROLE_IN_AUDIT_TEAM,
        variables={
            'input': dict(
                auditId=audit.id, auditorEmail=auditor.user.email, role=REVIEWER
            )
        },
    )
    response_auditor_email = response['data']['updateAuditorRoleInAuditTeam'][
        'auditAuditor'
    ]['auditor']['user']['email']
    assert response_auditor_email == auditor.user.email


@pytest.mark.functional(permissions=['audit.assign_audit'])
def test_update_auditor_role_in_audit_team_to_lead_auditor(
    graphql_audit_client, audit, auditor, auditor2
):
    AuditAuditor.objects.create(audit=audit, auditor=auditor, title_role='lead_auditor')
    AuditAuditor.objects.create(audit=audit, auditor=auditor2, title_role='tester')

    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_ROLE_IN_AUDIT_TEAM,
        variables={
            'input': dict(
                auditId=audit.id, auditorEmail=auditor2.user.email, role=LEAD_AUDITOR
            )
        },
    )
    assert response['errors'] is not None


@pytest.mark.functional(permissions=['audit.update_audit_user_preferences'])
def test_update_auditor_user_preferences(graphql_audit_client, auditor_user):
    user_preferences = {
        'requirements': {
            'filters': [
                {
                    'id': 'ID',
                    'value': 'LCL-7',
                    'column': 'ID',
                    'component': 'text',
                    'condition': 'is',
                    'columnType': 'TEXT',
                }
            ]
        }
    }

    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_USER_PREFERENCES,
        variables={
            'input': dict(
                email=auditor_user.user.email,
                userPreferences=json.dumps(user_preferences),
            )
        },
    )

    new_preferences = response['data']['updateAuditorUserPreferences']['preferences']
    user = User.objects.get(email=auditor_user.user.email)

    assert new_preferences == json.dumps(user.user_preferences)


@pytest.mark.functional(permissions=['audit.update_audit_user_preferences'])
def test_update_auditor_admin_user_preferences(
    graphql_audit_client, auditor_admin_user
):
    user_preferences = {
        'requirements': {
            'filters': [
                {
                    'id': 'ID',
                    'value': 'LCL-7',
                    'column': 'ID',
                    'component': 'text',
                    'condition': 'is',
                    'columnType': 'TEXT',
                }
            ]
        }
    }

    response = graphql_audit_client.execute(
        UPDATE_AUDITOR_USER_PREFERENCES,
        variables={
            'input': dict(
                email=auditor_admin_user.user.email,
                userPreferences=json.dumps(user_preferences),
            )
        },
    )

    new_preferences = response['data']['updateAuditorUserPreferences']['preferences']
    user = User.objects.get(email=auditor_admin_user.user.email)

    assert new_preferences == json.dumps(user.user_preferences)
