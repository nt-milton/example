import tempfile

import pytest
from django.core.files import File

from fieldwork.constants import (
    LAIKA_EVIDENCE_SOURCE_TYPE,
    MONITOR_SOURCE_TYPE,
    OBJECT_SOURCE_TYPE,
    OTHER_SOURCE_TYPE,
)
from fieldwork.models import Attachment, Evidence
from integration.models import PAYROLL, PROJECT_MANAGEMENT

from .mutations import ADD_EVIDENCE_ATTACHMENT


@pytest.fixture
def test_monitor_files():
    file_1 = File(
        file=tempfile.TemporaryFile(),
        name='[Integration Users] All Github users have MFA.pdf',
    )
    file_2 = File(
        file=tempfile.TemporaryFile(),
        name='[AWS] s3 buckets are not publicly available.pdf',
    )

    return [file_1, file_2]


@pytest.fixture
def test_lo_files():
    file_1 = File(file=tempfile.TemporaryFile(), name='TEST_ACCOUNT_12232.pdf')
    file_2 = File(file=tempfile.TemporaryFile(), name='TEST_DEVICE_12232.pdf')

    return [file_1, file_2]


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_add_evidence_attachment_with_monitors_metrics(
    graphql_client,
    evidence,
    organization_monitor,
    organization_monitor2,
    monitor_result1,
    monitor_result2,
):
    add_evidence_input = {
        'input': dict(
            id=str(evidence.id),
            monitors=[
                {
                    'id': organization_monitor.id,
                    'name': organization_monitor.name,
                },
                {
                    'id': organization_monitor2.id,
                    'name': organization_monitor2.name,
                },
            ],
            timeZone='UTC',
        )
    }

    graphql_client.execute(ADD_EVIDENCE_ATTACHMENT, variables=add_evidence_input)
    updated_evidence = Evidence.objects.get(id=evidence.id)

    metrics = updated_evidence.metrics.first()

    assert metrics.monitors_count == 2


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_add_evidence_attachment_with_monitors_files_metrics(
    graphql_client,
    evidence,
    test_monitor_files,
):
    add_evidence_input = {
        'input': dict(
            id=str(evidence.id),
            uploadedFiles=[
                dict(fileName=test_monitor_files[0].name, file='testFile'),
                dict(fileName=test_monitor_files[1].name, file='testFileXert'),
            ],
            timeZone='UTC',
        )
    }

    graphql_client.execute(ADD_EVIDENCE_ATTACHMENT, variables=add_evidence_input)
    updated_evidence = Evidence.objects.get(id=evidence.id)

    metrics = updated_evidence.metrics.first()

    assert metrics.monitors_count == 2


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_add_attachment_with_monitors_and_monitors_files_metrics(
    graphql_client,
    evidence,
    test_monitor_files,
    organization_monitor,
    organization_monitor2,
    monitor_result1,
    monitor_result2,
):
    add_evidence_input = {
        'input': dict(
            id=str(evidence.id),
            uploadedFiles=[
                dict(fileName=test_monitor_files[0].name, file='testFile'),
                dict(fileName=test_monitor_files[1].name, file='testFileXert'),
            ],
            monitors=[
                {
                    'id': organization_monitor.id,
                    'name': organization_monitor.name,
                },
                {
                    'id': organization_monitor2.id,
                    'name': organization_monitor2.name,
                },
            ],
            timeZone='UTC',
        )
    }

    graphql_client.execute(ADD_EVIDENCE_ATTACHMENT, variables=add_evidence_input)
    updated_evidence = Evidence.objects.get(id=evidence.id)

    metrics = updated_evidence.metrics.first()

    assert metrics.monitors_count == 4


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_add_evidence_attachment_with_LO_files(graphql_client, evidence, test_lo_files):
    add_evidence_input = {
        'input': dict(
            id=str(evidence.id),
            uploadedFiles=[
                dict(fileName=test_lo_files[0].name, file='testFile'),
                dict(fileName=test_lo_files[1].name, file='testFileXert'),
            ],
            timeZone='UTC',
        )
    }

    graphql_client.execute(ADD_EVIDENCE_ATTACHMENT, variables=add_evidence_input)
    updated_evidence = Evidence.objects.get(id=evidence.id)

    metrics = updated_evidence.metrics.first()
    integration_metrics = metrics.integrations_counter

    assert integration_metrics['general'] == 2


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_add_evidence_lo_attachment(
    graphql_client,
    evidence,
    lo_for_device_type,
    lo_for_account_type,
    lo_for_device_type_manual,
    lo_device,
    lo_account,
):
    add_evidence_input = {
        'input': dict(
            id=str(evidence.id),
            objectsIds=[str(lo_device.id), str(lo_account.id)],
            timeZone='UTC',
        )
    }

    graphql_client.execute(ADD_EVIDENCE_ATTACHMENT, variables=add_evidence_input)
    updated_evidence = Evidence.objects.get(id=evidence.id)

    metrics = updated_evidence.metrics.first()
    integration_metrics = metrics.integrations_counter

    assert integration_metrics[PAYROLL] == 1
    assert integration_metrics[PROJECT_MANAGEMENT] == 1
    assert integration_metrics['general'] == 1


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_add_evidence_lo_attachment_and_files(
    graphql_client,
    evidence,
    lo_for_device_type,
    lo_for_device_type_manual,
    lo_device,
    test_lo_files,
):
    add_evidence_input = {
        'input': dict(
            id=str(evidence.id),
            objectsIds=[
                str(lo_device.id),
            ],
            uploadedFiles=[
                dict(fileName=test_lo_files[0].name, file='testFile'),
                dict(fileName=test_lo_files[1].name, file='testFileXert'),
            ],
            timeZone='UTC',
        )
    }

    graphql_client.execute(ADD_EVIDENCE_ATTACHMENT, variables=add_evidence_input)
    updated_evidence = Evidence.objects.get(id=evidence.id)

    metrics = updated_evidence.metrics.first()
    integration_metrics = metrics.integrations_counter

    assert integration_metrics[PAYROLL] == 1
    assert integration_metrics['general'] == 3


@pytest.mark.functional(permissions=['fieldwork.change_evidence'])
def test_add_evidence_attachments_source(
    graphql_client,
    evidence,
    test_lo_files,
    document,
    vendor,
    officer,
    training,
    team,
    lo_for_device_type,
    lo_device,
    organization_monitor,
    monitor_result1,
    attachment_source_types,
):
    add_evidence_input = {
        'input': dict(
            id=str(evidence.id),
            uploadedFiles=[
                dict(fileName=test_lo_files[0].name, file='testFile'),
                dict(fileName=test_lo_files[1].name, file='testFileXert'),
            ],
            documents=[document.evidence.id],
            timeZone='UTC',
            officers=[officer.id],
            teams=[team.id],
            objectsIds=[str(lo_device.id)],
            vendors=[vendor.id],
            trainings=[training.id],
            monitors=[
                {
                    'id': organization_monitor.id,
                    'name': organization_monitor.name,
                }
            ],
        )
    }

    graphql_client.execute(ADD_EVIDENCE_ATTACHMENT, variables=add_evidence_input)

    attachments = Attachment.objects.filter(evidence=evidence)
    assert attachments.count() == 10

    lo_attach = attachments.filter(source__name=OBJECT_SOURCE_TYPE)
    monitor_attach = attachments.filter(source__name=MONITOR_SOURCE_TYPE)
    laika_ev_attach = attachments.filter(source__name=LAIKA_EVIDENCE_SOURCE_TYPE)
    other_attach = attachments.filter(source__name=OTHER_SOURCE_TYPE)

    assert lo_attach.count() == 1
    assert monitor_attach.count() == 1
    assert laika_ev_attach.count() == 5
    assert other_attach.count() == 3
