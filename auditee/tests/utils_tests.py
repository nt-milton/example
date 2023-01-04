import tempfile

import pytest
from django.core.files import File
from django.db.models import Q

from audit.constants import REVIEWER_AUDITOR_KEY, TESTER_AUDITOR_KEY
from audit.models import Audit, AuditAuditor, AuditFirm
from audit.utils.incredible_filter import get_incredible_filter
from auditee.utils import (
    add_attachment_file_to_evidence,
    create_officers_log_file,
    create_tmp_attachment,
    create_vendors_log_file,
    delete_audit_tmp_attachments,
    exists_laika_object,
    get_draft_report_alert_and_email_receivers,
    get_er_metrics_for_fetch,
    get_order_by,
    get_results_from_query,
    handle_laika_object_fetch,
    handle_monitors_fetch,
    handle_officers_log_fetch,
    handle_vendors_log_fetch,
    run_fetch_for_other_types,
    update_description_for_evs,
    update_fetch_accuracy_for_evs,
    update_metrics_for_fetch,
)
from fieldwork.constants import (
    LAIKA_EVIDENCE_SOURCE_TYPE,
    MONITOR_FETCH_TYPE,
    OBJECT_SOURCE_TYPE,
    OFFICER_FETCH_TYPE,
    VENDOR_FETCH_TYPE,
)
from fieldwork.models import Evidence, EvidenceMetric, FetchLogic, TemporalAttachment
from fieldwork.tests.factory import create_tmp_attachment_factory
from fieldwork.util.evidence_attachment import add_laika_objects_attachments
from integration.models import PAYROLL
from monitor.tests.factory import create_monitor_result
from objects.models import LaikaObjectType
from user.constants import AUDITOR, AUDITOR_ADMIN
from user.models import Auditor, Officer
from user.tests import create_user
from user.tests.factory import create_user_auditor
from vendor.models import OrganizationVendor
from vendor.tests.factory import create_vendor

VENDOR_NAME = 'AWS'
VENDOR_RENAME = 'CLOUD AWS'
OFFICER_NAME = 'SECURITY COMMITTEE'
OFFICER_RENAME = 'PRIVACY COMMITTEE'


@pytest.fixture()
def lo_types_set_up(graphql_organization):
    LaikaObjectType.objects.create(
        organization=graphql_organization,
        display_name='object_device',
        display_index=1,
        type_name='device',
    )

    LaikaObjectType.objects.create(
        organization=graphql_organization,
        display_name='object_account',
        display_index=2,
        type_name='account',
    )


@pytest.fixture
def fetch_logic(audit):
    return FetchLogic.objects.create(
        code='FL-1',
        type='object_device',
        logic={'query': 'select lo_devices.name from lo_devices;'},
        audit=audit,
        description='Laika Object devices results',
    )


@pytest.fixture
def fetch_logic_lo_account(audit):
    return FetchLogic.objects.create(
        code='FL-2',
        type='object_account',
        logic={'query': 'select * from lo_accounts;'},
        audit=audit,
    )


@pytest.fixture
def fetch_logic_monitor(audit, organization_monitor):
    return FetchLogic.objects.create(
        code='FL-3',
        type='monitor',
        logic={
            'query': (
                'select monitor_id from monitors where monitor_id= '
                f'{organization_monitor.monitor.id};'
            )
        },
        audit=audit,
        description='Monitor with results',
    )


@pytest.fixture
def fetch_logic_flagged_monitor(audit, organization_monitor_flagged):
    return FetchLogic.objects.create(
        code='FL-3',
        type='monitor',
        logic={
            'query': (
                'select monitor_id from monitors where monitor_id= '
                f'{organization_monitor_flagged.monitor.id};'
            )
        },
        audit=audit,
        description='Monitor with results',
    )


@pytest.fixture
def fetch_logic_monitor2(audit, organization_monitor, organization_monitor2):
    return FetchLogic.objects.create(
        code='FL-4',
        type='monitor',
        logic={
            'query': (
                'select monitor_id from monitors where monitor_id= '
                f'{organization_monitor.id} OR monitor_id= '
                f'{organization_monitor2.id};'
            )
        },
        audit=audit,
        description='Monitor with results',
    )


@pytest.fixture
def tmp_attachment(fetch_logic_object_device):
    name = 'test.pdf'
    return create_tmp_attachment_factory(fetch_logic_object_device, name)


@pytest.fixture
def tmp_attachment_2(fetch_logic_object_device):
    name = 'test 2.pdf'
    return create_tmp_attachment_factory(fetch_logic_object_device, name)


@pytest.fixture
def evidence(graphql_organization, audit):
    return Evidence.objects.create(
        audit=audit, display_id='2', name='Ev2', instructions='yyyy', status='open'
    )


@pytest.fixture
def fetch_logic_officer_log(audit):
    return FetchLogic.objects.create(
        code='FL-2',
        type=OFFICER_FETCH_TYPE,
        logic={'query': 'select officers.title from officers;'},
        audit=audit,
    )


@pytest.fixture
def fetch_logic_vendor_log(audit):
    return FetchLogic.objects.create(
        code='FL-2',
        type=VENDOR_FETCH_TYPE,
        logic={'query': 'select vendors.name from vendors;'},
        audit=audit,
    )


@pytest.fixture
def owner(graphql_organization):
    user = create_user(graphql_organization, email='evidence_test@heylaika.com')
    user.first_name = 'First Name'
    user.last_name = 'Last Name'
    user.save()
    return user


@pytest.fixture
def officer(graphql_organization, owner):
    return Officer.objects.create(
        organization=graphql_organization, user=owner, name=OFFICER_NAME
    )


@pytest.fixture
def vendor(graphql_organization):
    vendor = create_vendor(
        name=VENDOR_NAME,
        website='www.new-vendor.com',
        description='This is a new vendor',
        is_public=True,
    )
    OrganizationVendor.objects.create(vendor=vendor, organization=graphql_organization)
    return vendor


@pytest.fixture
def auditor_user_reviewer_in_audit_team(
    graphql_audit_firm: AuditFirm, audit: Audit
) -> Auditor:
    auditor = create_user_auditor(
        email='auditor_user_reviewer_in_team@heylaika.com',
        role=AUDITOR,
        with_audit_firm=True,
        audit_firm=graphql_audit_firm.name,
    )
    AuditAuditor.objects.create(
        auditor=auditor, audit=audit, title_role=REVIEWER_AUDITOR_KEY
    )
    return auditor


@pytest.fixture
def auditor_user_tester_in_audit_team(
    graphql_audit_firm: AuditFirm, audit: Audit
) -> Auditor:
    auditor = create_user_auditor(
        email='auditor_user_tester_in_team@heylaika.com',
        role=AUDITOR,
        with_audit_firm=True,
        audit_firm=graphql_audit_firm.name,
    )
    AuditAuditor.objects.create(
        auditor=auditor, audit=audit, title_role=TESTER_AUDITOR_KEY
    )
    return auditor


@pytest.fixture
def auditor_user_not_in_audit_team(
    graphql_audit_firm: AuditFirm, audit: Audit
) -> Auditor:
    return create_user_auditor(
        email='auditor_user_not_in_team@heylaika.com',
        role=AUDITOR,
        with_audit_firm=True,
        audit_firm=graphql_audit_firm.name,
    )


@pytest.fixture
def auditor_admin_user(graphql_audit_firm: AuditFirm) -> Auditor:
    return create_user_auditor(
        email='auditoradmin@heylaika.com',
        role=AUDITOR_ADMIN,
        with_audit_firm=True,
        audit_firm=graphql_audit_firm.name,
    )


@pytest.fixture
def empty_er_metrics(evidence):
    return EvidenceMetric.objects.create(
        evidence_request=evidence, monitors_count=0, integrations_counter={'general': 0}
    )


@pytest.mark.functional
def test_exists_laika_object_is_false(graphql_organization, fetch_logic_object_device):
    exist_lo = exists_laika_object(graphql_organization, fetch_logic_object_device)
    assert exist_lo is False


@pytest.mark.functional
def test_get_results_from_query_when_lo_type(
    graphql_organization, fetch_logic_object_device
):
    res, query = get_results_from_query(graphql_organization, fetch_logic_object_device)
    assert len(res) == 0
    assert query == ''


@pytest.mark.functional
def test_get_results_from_query_when_officer_type(
    graphql_organization, fetch_logic_officer_log
):
    res, query = get_results_from_query(graphql_organization, fetch_logic_officer_log)
    query_res = query.replace("\n", "")
    query_res = query_res.replace("   ", " ")
    query_gen = (
        'select officers.title from (  select  o.id as officer_id,  '
        'o.created_at,  o.updated_at,  o.name as title,  '
        'o.description,  '
        'u.first_name,  u.last_name  from user_officer as o  '
        'left join user_user as u on u.id = o.user_id  '
        f'where o.organization_id = \'{graphql_organization.id}\'  ) '
        'AS officers;'
    )
    assert len(res) == 0
    assert query_res == query_gen.strip()


@pytest.mark.functional
def test_add_attachment_file_to_evidence(
    evidence, fetch_logic_object_device, tmp_attachment
):
    add_attachment_file_to_evidence(evidence, attachment=tmp_attachment)
    assert evidence.attachments.count() == 1
    assert evidence.attachments.first().from_fetch is True


@pytest.mark.functional
def test_create_tmp_attachment(fetch_logic_object_device):
    name = 'test.pdf'
    file = File(file=tempfile.TemporaryFile(), name=name)
    attachment = create_tmp_attachment(fetch_logic_object_device, name, file.read())
    assert attachment.name == name
    assert attachment.fetch_logic.code == fetch_logic_object_device.code


@pytest.mark.functional
def test_create_officers_log_file(officer):
    file_name, file = create_officers_log_file([officer], 'UTC')
    assert file_name.index('Officers Details_') != -1


@pytest.mark.functional
def test_create_vendors_log_file(graphql_organization):
    vendors = graphql_organization.organization_vendors.all()
    file_name, file = create_vendors_log_file(graphql_organization, vendors, 'UTC')
    assert file_name.index('vendors_log_') != -1


@pytest.mark.functional
def test_run_fetch_for_other_types_attachments_exist(
    graphql_organization,
    evidence,
    fetch_logic_object_device,
    tmp_attachment,
    tmp_attachment_2,
):
    query = ''
    results = ['android', 'ios']
    run_fetch_for_other_types(
        graphql_organization,
        evidence,
        fetch_logic_object_device,
        results,
        query,
        'UTC',
        {},
    )
    assert evidence.attachments.count() == 2


@pytest.mark.functional
def test_run_fetch_for_other_types_vendor_type(
    graphql_organization, evidence, fetch_logic_vendor_log
):
    query = ''
    results = ['Slack', 'AWS']
    run_fetch_for_other_types(
        graphql_organization, evidence, fetch_logic_vendor_log, results, query, 'UTC'
    )
    attachment = evidence.attachments.first()
    assert evidence.attachments.count() == 1
    assert attachment.name.index('vendors_log_') != -1
    assert attachment.from_fetch is True


@pytest.mark.functional
def test_delete_audit_tmp_attachments(audit, tmp_attachment):
    assert len(TemporalAttachment.objects.filter(audit=audit)) == 1
    delete_audit_tmp_attachments(audit)
    assert len(TemporalAttachment.objects.filter(audit=audit)) == 0


@pytest.mark.functional
def test_update_fetch_accuracy_for_evs(
    graphql_organization, evidence, fetch_logic_object_device, tmp_attachment
):
    evidence.add_attachment(tmp_attachment)
    update_fetch_accuracy_for_evs([evidence])

    assert evidence.is_fetch_logic_accurate is True
    assert evidence.run_account_lo_fetch == 'run'


@pytest.mark.functional
def test_update_description_for_evs(
    graphql_organization, evidence, fetch_logic_object_device
):
    evidence.fetch_logic.add(fetch_logic_object_device)
    update_description_for_evs([evidence])

    assert evidence.description == 'Laika Object devices results'


@pytest.mark.functional
def test_handle_laika_object_fetch_results_empty(
    graphql_organization, evidence, fetch_logic_object_device
):
    query = ''
    results = []
    handle_laika_object_fetch(
        graphql_organization, fetch_logic_object_device, evidence, results, query, 'UTC'
    )
    assert evidence.attachments.count() == 0
    assert evidence.run_account_lo_fetch == 'skip'


@pytest.mark.functional
def test_handle_laika_object_fetch_with_results(
    graphql_organization, evidence, lo_types_set_up, fetch_logic_object_device
):
    query = 'select lo_devices.name from lo_devices;'
    results = ['object_device']
    handle_laika_object_fetch(
        graphql_organization, fetch_logic_object_device, evidence, results, query, 'UTC'
    )
    attachment_qs = evidence.attachments
    assert attachment_qs.count() == 1
    assert evidence.run_account_lo_fetch == 'still_run'
    assert attachment_qs.first().origin_source_object is not None


@pytest.mark.functional
def test_handle_laika_object_fetch_results_not_empty(
    graphql_organization, evidence, fetch_logic_object_device, fetch_logic_lo_account
):
    query = ''
    results_fl = []
    results_fl2 = ['res']
    handle_laika_object_fetch(
        graphql_organization,
        fetch_logic_object_device,
        evidence,
        results_fl,
        query,
        'UTC',
    )
    handle_laika_object_fetch(
        graphql_organization,
        fetch_logic_lo_account,
        evidence,
        results_fl2,
        query,
        'UTC',
    )

    assert evidence.attachments.count() == 0
    assert evidence.run_account_lo_fetch == 'skip'


@pytest.mark.functional
def test_handle_monitors_fetch_no_results(
    graphql_organization, evidence, fetch_logic_monitor, organization_monitor
):
    results = [organization_monitor.id]
    create_monitor_result(
        organization_monitor=organization_monitor,
        result={'columns': ['id'], 'data': []},
    )
    handle_monitors_fetch(
        graphql_organization, fetch_logic_monitor, evidence, results, 'UTC'
    )

    assert evidence.attachments.count() == 0


@pytest.mark.functional
def test_fetch_runs_first_time_for_monitor(
    graphql_organization, evidence, fetch_logic_monitor, organization_monitor
):
    results = [organization_monitor.id]
    create_monitor_result(
        organization_monitor=organization_monitor,
        result={'columns': ['id'], 'data': ['123']},
    )
    handle_monitors_fetch(
        graphql_organization, fetch_logic_monitor, evidence, results, 'UTC'
    )

    attachment_qs = evidence.attachments
    assert attachment_qs.count() == 1
    assert evidence.attachments.first().from_fetch is True
    assert attachment_qs.first().origin_source_object == organization_monitor.monitor


@pytest.mark.functional
def test_fetch_runs_second_time_for_monitor(
    graphql_organization, evidence, fetch_logic_monitor, organization_monitor
):
    results = [organization_monitor.id]
    create_monitor_result(
        organization_monitor=organization_monitor,
        result={'columns': ['id'], 'data': ['123']},
    )
    handle_monitors_fetch(
        graphql_organization, fetch_logic_monitor, evidence, results, 'UTC'
    )
    assert evidence.attachments.count() == 1
    create_monitor_result(
        organization_monitor=organization_monitor,
        result={'columns': ['id'], 'data': ['123']},
    )
    handle_monitors_fetch(
        graphql_organization, fetch_logic_monitor, evidence, results, 'UTC'
    )
    # Attachment is still 1 because the previous attachment was deleted
    assert evidence.attachments.count() == 1


@pytest.mark.functional
def test_fetch_runs_after_renaming_monitor(
    graphql_organization, evidence, fetch_logic_monitor, organization_monitor
):
    results = [organization_monitor.id]
    create_monitor_result(
        organization_monitor=organization_monitor,
        result={'columns': ['id'], 'data': ['123']},
    )
    handle_monitors_fetch(
        graphql_organization, fetch_logic_monitor, evidence, results, 'UTC'
    )

    attachment = evidence.attachments.first()
    assert evidence.attachments.count() == 1
    attachment.name = 'Monitor Renamed.xlsx'
    attachment.save()
    create_monitor_result(
        organization_monitor=organization_monitor,
        result={'columns': ['id'], 'data': ['123']},
    )
    handle_monitors_fetch(
        graphql_organization, fetch_logic_monitor, evidence, results, 'UTC'
    )
    assert evidence.attachments.count() == 2


@pytest.mark.functional
def test_fetch_runs_after_submitting_er_with_monitor(
    graphql_organization, evidence, fetch_logic_monitor, organization_monitor
):
    results = [organization_monitor.id]
    create_monitor_result(
        organization_monitor=organization_monitor,
        result={'columns': ['id'], 'data': ['123']},
    )
    handle_monitors_fetch(
        graphql_organization, fetch_logic_monitor, evidence, results, 'UTC'
    )

    attachment = evidence.attachments.first()
    assert evidence.attachments.count() == 1
    attachment.has_been_submitted = True
    attachment.save()
    create_monitor_result(
        organization_monitor=organization_monitor,
        result={'columns': ['id'], 'data': ['123']},
    )
    handle_monitors_fetch(
        graphql_organization, fetch_logic_monitor, evidence, results, 'UTC'
    )
    assert evidence.attachments.count() == 2


@pytest.mark.functional
def test_handle_flagged_monitors_fetch(
    graphql_organization,
    evidence,
    fetch_logic_monitor,
    organization_monitor,
    organization_monitor_flagged,
    fetch_logic_flagged_monitor,
):
    results = [organization_monitor.id, organization_monitor_flagged.id]
    create_monitor_result(
        organization_monitor=organization_monitor,
        result={'columns': ['id'], 'data': [[]]},
    )
    create_monitor_result(
        organization_monitor=organization_monitor_flagged,
        result={'columns': ['id'], 'data': [[]]},
    )
    handle_monitors_fetch(
        graphql_organization, fetch_logic_flagged_monitor, evidence, results, 'UTC'
    )

    assert evidence.attachments.count() == 1


@pytest.mark.functional
def test_get_draft_report_alert_and_email_receivers(
    auditor_admin_user,
    auditor_user_not_in_audit_team,
    auditor_user_reviewer_in_audit_team,
    auditor_user_tester_in_audit_team,
    audit,
):
    assert len(get_draft_report_alert_and_email_receivers(audit.id)) == 2


@pytest.mark.functional
def test_handle_monitors_fetch_metrics(
    graphql_organization,
    evidence,
    fetch_logic_monitor2,
    organization_monitor,
    organization_monitor2,
    empty_er_metrics,
):
    results = [organization_monitor.id, organization_monitor2.id]
    create_monitor_result(
        organization_monitor=organization_monitor,
        result={'columns': ['id'], 'data': ['123']},
    )
    create_monitor_result(
        organization_monitor=organization_monitor2,
        result={'columns': ['id'], 'data': ['456']},
    )

    handle_monitors_fetch(
        organization=graphql_organization,
        fetch_logic=fetch_logic_monitor2,
        ev_request=evidence,
        results=results,
        timezone='UTC',
        monitors_count=0,
    )

    metrics = evidence.metrics.first()

    assert metrics.monitors_count == 2


@pytest.mark.django_db
def test_get_cleared_metrics_for_fetch(evidence):
    metrics = get_er_metrics_for_fetch(evidence)

    assert metrics['monitors_count'] == 0
    assert metrics['integrations_counter'] == {'general': 0}


@pytest.mark.django_db
def test_get_current_metrics_for_fetch(evidence, er_metrics):
    metrics = get_er_metrics_for_fetch(evidence, True)

    assert metrics['monitors_count'] == 2
    assert metrics['integrations_counter'][PAYROLL] == 1
    assert metrics['integrations_counter']['general'] == 2


@pytest.mark.django_db
def test_updated_metrics_for_fetch_when_first_time(evidence, empty_er_metrics):
    metrics_dict = {
        'monitors_count': empty_er_metrics.monitors_count,
        'integrations_counter': empty_er_metrics.integrations_counter,
    }
    metrics = update_metrics_for_fetch(evidence, metrics_dict, 0)

    assert metrics['monitors_count'] == 0
    assert metrics['integrations_counter'] == {'general': 0}


@pytest.mark.django_db
def test_updated_metrics_for_fetch(evidence, er_metrics):
    metrics_dict = {'monitors_count': 0, 'integrations_counter': None}
    metrics = update_metrics_for_fetch(evidence, metrics_dict, 1)

    assert metrics['monitors_count'] == 2
    assert metrics['integrations_counter'][PAYROLL] == 1
    assert metrics['integrations_counter']['general'] == 2


@pytest.mark.functional
def test_fetch_runs_first_time_for_laika_object(
    graphql_organization, lo_device, fetch_logic_object_device, evidence_no_attachments
):
    results = [(1, None, 'Test ', 'Desktop', 'true', '12345')]
    handle_laika_object_fetch(
        organization=graphql_organization,
        fetch_logic=fetch_logic_object_device,
        ev_request=evidence_no_attachments,
        results=results,
        query='',
        timezone='UTC',
    )

    assert evidence_no_attachments.attachments.count() == 1
    assert evidence_no_attachments.attachments.first().from_fetch is True


@pytest.mark.functional
def test_fetch_runs_second_time_for_laika_object(
    graphql_organization,
    lo_device,
    lo_account,
    fetch_logic_object_device,
    evidence_no_attachments,
):
    results = [(1, None, 'Test ', 'Desktop', 'true', '12345')]
    lo_device_file_name = (
        f'{graphql_organization.name.upper()}_{lo_device.type_name.upper()}_'
    )

    lo_account_file_name = (
        f'{graphql_organization.name.upper()}_{lo_account.type_name.upper()}_'
    )
    # This attachment will be replaced by the new fetch
    evidence_no_attachments.add_attachment(
        file_name=lo_device_file_name,
        file=File(file=tempfile.TemporaryFile(), name=lo_device_file_name),
        is_from_fetch=True,
    )
    evidence_no_attachments.add_attachment(
        file_name=lo_account_file_name,
        file=File(file=tempfile.TemporaryFile(), name=lo_account_file_name),
        is_from_fetch=True,
    )

    assert evidence_no_attachments.attachments.count() == 2

    handle_laika_object_fetch(
        organization=graphql_organization,
        fetch_logic=fetch_logic_object_device,
        ev_request=evidence_no_attachments,
        results=results,
        query='',
        timezone='UTC',
    )

    assert evidence_no_attachments.attachments.count() == 2


@pytest.mark.functional
def test_fetch_runs_after_renaming_laika_object(
    graphql_organization, lo_device, fetch_logic_object_device, evidence_no_attachments
):
    results = [(1, None, 'Test ', 'Desktop', 'true', '12345')]
    lo_device_file_name = (
        f'{graphql_organization.name.upper()}_{lo_device.type_name.upper()}_'
    )

    # This attachment will not be replaced by the new fetch because the file
    # will be renamed
    evidence_no_attachments.add_attachment(
        file_name=lo_device_file_name,
        file=File(file=tempfile.TemporaryFile(), name=lo_device_file_name),
        is_from_fetch=True,
    )
    attachment = evidence_no_attachments.attachments.all().first()
    attachment.name = 'LO_Test_File.xlsx'
    attachment.save()

    assert evidence_no_attachments.attachments.count() == 1

    handle_laika_object_fetch(
        organization=graphql_organization,
        fetch_logic=fetch_logic_object_device,
        ev_request=evidence_no_attachments,
        results=results,
        query='',
        timezone='UTC',
    )

    assert evidence_no_attachments.attachments.count() == 2


@pytest.mark.functional
def test_fetch_runs_after_submitting_er_with__laika_object(
    graphql_organization, lo_device, fetch_logic_object_device, evidence_no_attachments
):
    results = [(1, None, 'Test ', 'Desktop', 'true', '12345')]
    lo_device_file_name = (
        f'{graphql_organization.name.upper()}_{lo_device.type_name.upper()}_'
    )

    # This attachment will not be replaced by the new fetch because the file
    # will be renamed
    evidence_no_attachments.add_attachment(
        file_name=lo_device_file_name,
        file=File(file=tempfile.TemporaryFile(), name=lo_device_file_name),
        is_from_fetch=True,
    )
    attachment = evidence_no_attachments.attachments.all().first()
    attachment.has_been_submitted = True
    attachment.save()

    assert evidence_no_attachments.attachments.count() == 1

    handle_laika_object_fetch(
        organization=graphql_organization,
        fetch_logic=fetch_logic_object_device,
        ev_request=evidence_no_attachments,
        results=results,
        query='',
        timezone='UTC',
    )

    assert evidence_no_attachments.attachments.count() == 2


@pytest.mark.functional
def test_add_laika_objects_attachments(
    evidence,
    lo_device,
    lo_for_device_type,
    graphql_organization,
):
    ids, _, _ = add_laika_objects_attachments(
        fieldwork_evidence=evidence,
        objects_ids=[lo_device.id],
        organization=graphql_organization,
        time_zone='UTC',
    )
    assert evidence.attachments.count() == 1
    assert evidence.attachments.first().from_fetch is False


@pytest.mark.functional
def test_lo_fetch_metrics(
    graphql_organization,
    lo_device,
    lo_for_device_type,
    lo_for_device_type_manual,
    fetch_logic_object_device,
    evidence,
    empty_er_metrics,
):
    results = [
        (1, None, 'Test ', 'Desktop', 'true', '12345'),
        (2, None, 'Test2 ', 'Desktop', 'false', '123455'),
    ]
    handle_laika_object_fetch(
        graphql_organization,
        fetch_logic_object_device,
        evidence,
        results,
        query='',
        timezone='UTC',
    )

    metrics = Evidence.objects.get(id=evidence.id).metrics.first()
    integration_metrics = metrics.integrations_counter
    assert integration_metrics[PAYROLL] == 1
    assert integration_metrics['general'] == 1


@pytest.mark.functional
def test_fetch_runs_first_time_for_officer_log(
    graphql_organization, fetch_logic_officer_log, evidence_no_attachments, officer
):
    handle_officers_log_fetch(
        graphql_organization, fetch_logic_officer_log, evidence_no_attachments, 'UTC'
    )
    assert evidence_no_attachments.attachments.count() == 1
    assert evidence_no_attachments.attachments.first().from_fetch is True


@pytest.mark.functional
def test_fetch_runs_second_time_for_officer_log(
    graphql_organization, fetch_logic_officer_log, evidence_no_attachments, officer
):
    handle_officers_log_fetch(
        graphql_organization, fetch_logic_officer_log, evidence_no_attachments, 'UTC'
    )
    assert evidence_no_attachments.attachments.count() == 1
    handle_officers_log_fetch(
        graphql_organization, fetch_logic_officer_log, evidence_no_attachments, 'UTC'
    )
    assert evidence_no_attachments.attachments.count() == 1


@pytest.mark.functional
def test_fetch_runs_after_renaming_for_officer_log(
    graphql_organization, fetch_logic_officer_log, evidence_no_attachments, officer
):
    handle_officers_log_fetch(
        graphql_organization, fetch_logic_officer_log, evidence_no_attachments, 'UTC'
    )
    assert evidence_no_attachments.attachments.count() == 1
    attachment = evidence_no_attachments.attachments.first()
    attachment.name = OFFICER_RENAME
    attachment.save()

    handle_officers_log_fetch(
        graphql_organization, fetch_logic_officer_log, evidence_no_attachments, 'UTC'
    )
    assert evidence_no_attachments.attachments.count() == 2


@pytest.mark.functional
def test_fetch_runs_after_submitting_er_with_officer_log(
    graphql_organization, fetch_logic_officer_log, evidence_no_attachments, officer
):
    handle_officers_log_fetch(
        graphql_organization, fetch_logic_officer_log, evidence_no_attachments, 'UTC'
    )
    assert evidence_no_attachments.attachments.count() == 1
    attachment = evidence_no_attachments.attachments.first()
    attachment.has_been_submitted = True
    attachment.save()

    handle_officers_log_fetch(
        graphql_organization, fetch_logic_officer_log, evidence_no_attachments, 'UTC'
    )
    assert evidence_no_attachments.attachments.count() == 2


@pytest.mark.functional
def test_fetch_runs_first_time_for_vendor_log(
    graphql_organization, fetch_logic_vendor_log, evidence_no_attachments, vendor
):
    handle_vendors_log_fetch(
        graphql_organization, fetch_logic_vendor_log, evidence_no_attachments, 'UTC'
    )
    assert evidence_no_attachments.attachments.count() == 1
    assert evidence_no_attachments.attachments.first().from_fetch is True


@pytest.mark.functional
def test_fetch_runs_second_time_for_vendor_log(
    graphql_organization, fetch_logic_vendor_log, evidence_no_attachments, vendor
):
    handle_vendors_log_fetch(
        graphql_organization, fetch_logic_vendor_log, evidence_no_attachments, 'UTC'
    )
    assert evidence_no_attachments.attachments.count() == 1
    handle_vendors_log_fetch(
        graphql_organization, fetch_logic_vendor_log, evidence_no_attachments, 'UTC'
    )
    assert evidence_no_attachments.attachments.count() == 1


@pytest.mark.functional
def test_fetch_runs_after_renaming_for_vendor_log(
    graphql_organization, fetch_logic_vendor_log, evidence_no_attachments, vendor
):
    handle_vendors_log_fetch(
        graphql_organization, fetch_logic_vendor_log, evidence_no_attachments, 'UTC'
    )
    assert evidence_no_attachments.attachments.count() == 1
    attachment = evidence_no_attachments.attachments.first()
    attachment.name = VENDOR_RENAME
    attachment.save()

    handle_vendors_log_fetch(
        graphql_organization, fetch_logic_vendor_log, evidence_no_attachments, 'UTC'
    )
    assert evidence_no_attachments.attachments.count() == 2


@pytest.mark.functional
def test_fetch_runs_after_submitting_er_with_vendor_log(
    graphql_organization, fetch_logic_vendor_log, evidence_no_attachments, vendor
):
    handle_vendors_log_fetch(
        graphql_organization, fetch_logic_vendor_log, evidence_no_attachments, 'UTC'
    )
    assert evidence_no_attachments.attachments.count() == 1
    attachment = evidence_no_attachments.attachments.first()
    attachment.has_been_submitted = True
    attachment.save()

    handle_vendors_log_fetch(
        graphql_organization, fetch_logic_vendor_log, evidence_no_attachments, 'UTC'
    )
    assert evidence_no_attachments.attachments.count() == 2


@pytest.mark.functional
@pytest.mark.parametrize(
    'order, field, prefix, is_descending',
    [('ascend', 'Name', '', False), ('descend', 'Created', 'data__', True)],
)
def test_get_order_by(order, field, prefix, is_descending):
    response = get_order_by(dict(order_by=dict(field=field, order=order)), prefix)

    order_field = f'{prefix}{field}'

    assert str(response) == f'OrderBy(F({order_field}), descending={is_descending})'


@pytest.mark.functional
def test_get_order_by_default():
    response = get_order_by(dict())

    assert str(response) == 'OrderBy(F(id), descending=False)'


@pytest.mark.functional
def test_get_incredible_filter_default():
    response = get_incredible_filter(dict())
    assert str(response) == str(Q())


@pytest.mark.functional
def test_get_incredible_filter():
    response = get_incredible_filter(
        dict(
            filters=[
                {
                    "field": "Contractor",
                    "value": 'false',
                    "operator": "is",
                    "type": "BOOLEAN",
                }
            ]
        )
    )

    assert str(response) == "(AND: (OR: (AND: ), (AND: ('Contractor', False))))"


@pytest.mark.django_db
def test_handle_monitors_fetch_source_type(
    graphql_organization,
    evidence,
    fetch_logic_monitor,
    organization_monitor,
):
    results = [organization_monitor.id]
    create_monitor_result(
        organization_monitor=organization_monitor,
        result={'columns': ['id'], 'data': [[]]},
    )

    handle_monitors_fetch(
        graphql_organization, fetch_logic_monitor, evidence, results, 'UTC'
    )

    assert evidence.attachments.count() == 1
    assert evidence.attachments.first().source.name == MONITOR_FETCH_TYPE


@pytest.mark.django_db
def test_handle_object_fetch_source_type(
    graphql_organization, evidence, lo_types_set_up, fetch_logic_object_device
):
    query = 'select lo_devices.name from lo_devices;'
    results = ['object_device']
    handle_laika_object_fetch(
        graphql_organization, fetch_logic_object_device, evidence, results, query, 'UTC'
    )
    assert evidence.attachments.count() == 1
    assert evidence.attachments.first().source.name == OBJECT_SOURCE_TYPE


@pytest.mark.functional
def test_store_source_when_temp_attachments_exist(
    graphql_organization,
    evidence,
    fetch_logic_object_device,
    tmp_attachment,
):
    query = ''
    results = ['android', 'ios']
    run_fetch_for_other_types(
        graphql_organization,
        evidence,
        fetch_logic_object_device,
        results,
        query,
        'UTC',
        {},
    )
    assert evidence.attachments.count() == 1
    assert evidence.attachments.first().source.name == OBJECT_SOURCE_TYPE


@pytest.mark.functional
def test_store_source_for_officer_attachment(
    graphql_organization,
    evidence,
    officer,
    fetch_logic_officer,
):
    query = ''
    results = ['Joe', 'Dan']
    run_fetch_for_other_types(
        graphql_organization, evidence, fetch_logic_officer, results, query, 'UTC', {}
    )
    assert evidence.attachments.count() == 1
    assert evidence.attachments.first().source.name == LAIKA_EVIDENCE_SOURCE_TYPE
