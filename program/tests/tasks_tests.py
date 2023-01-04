from unittest.mock import patch

import pytest

from certification.models import (
    ArchivedUnlockedOrganizationCertification,
    Certification,
    CertificationSection,
    UnlockedOrganizationCertification,
)
from certification.tests import create_certification
from program.models import SubTask
from program.tasks import refresh_organization_cache
from program.tests import (
    associate_certification_sections_to_subtask,
    associate_task_to_program,
    create_program,
    create_task,
)
from program.utils.program_progress import get_program_progress

ARGS = 0
UNLOCKED_SUBTASKS_ARG = 1


@pytest.fixture
def program(graphql_organization):
    return create_program(
        organization=graphql_organization,
        name='Privacy Program',
        description='This is an example of program',
    )


@pytest.fixture
def task(graphql_organization, program):
    return create_task(organization=graphql_organization, program=program)


@pytest.fixture(name="_certifications")
def fixture_certifications(graphql_organization):
    certification_1 = Certification.objects.create(name='SOC 1 type 2')
    certification_2 = Certification.objects.create(name='SOC 2 type 1')
    return certification_1, certification_2


@pytest.fixture(name="_unlocked_org_certification")
def fixture_unlocked_org_certification(graphql_organization, _certifications):
    certification_1, _ = _certifications
    return UnlockedOrganizationCertification.objects.create(
        organization=graphql_organization, certification=certification_1
    )


@pytest.fixture(name="_archived_unlocked_org_certification")
def fixture_archived_unlocked_org_certification(graphql_organization, _certifications):
    _, certification_2 = _certifications
    return ArchivedUnlockedOrganizationCertification.objects.create(
        organization=graphql_organization, certification=certification_2
    )


@pytest.fixture(name="_certification_sections")
def fixture_certification_sections(_certifications):
    certification_1, certification_2 = _certifications

    certification_section_1 = CertificationSection.objects.create(
        name='CC1.2', certification=certification_1
    )
    certification_section_2 = CertificationSection.objects.create(
        name='APO01.09', certification=certification_2
    )
    return certification_section_1, certification_section_2


@pytest.fixture(name='_subtasks')
def fixture_subtasks(task, _certification_sections):
    certification_section_1, certification_section_2 = _certification_sections
    subtask_1 = SubTask.objects.create(
        task=task,
        text='Subtask 1',
        status='completed',
        group='documentation',
        sort_index=1,
        badges='technical',
    )
    subtask_2 = SubTask.objects.create(
        task=task,
        text='Subtask 2',
        status='completed',
        group='documentation',
        sort_index=1,
        badges='technical',
    )
    subtask_1.certification_sections.add(certification_section_1)
    subtask_2.certification_sections.add(certification_section_2)
    return subtask_1, subtask_2


@pytest.mark.functional
def test_refresh_cache_program(
    graphql_client, graphql_organization, program, task, _subtasks
):
    subtask_1, _ = _subtasks
    soc2_sections = ['2.1', '3.1']
    soc2_cert_sections = create_certification(
        graphql_organization, soc2_sections, name='SOC 2 Type 2'
    ).sections.all()
    associate_certification_sections_to_subtask(subtask_1, soc2_cert_sections)
    associate_task_to_program(program, [task])
    result = refresh_organization_cache.delay(graphql_organization.id)
    assert result.get()['success'] is True


@pytest.mark.functional
def test_do_not_refresh_cache_program_if_not_org(
    graphql_client, graphql_organization, program, task, _subtasks
):
    try:
        result = refresh_organization_cache.delay()
        assert result.get('success') is None
    except Exception as exc:
        assert False, exc


@pytest.mark.functional
def test_refresh_cache_program_on_delete(
    graphql_client, graphql_organization, program, task, _subtasks
):
    subtask_1, _ = _subtasks
    soc2_sections = ['2.1', '3.1']
    soc2_cert_sections = create_certification(
        graphql_organization, soc2_sections, name='SOC 2 Type 2'
    ).sections.all()
    associate_certification_sections_to_subtask(subtask_1, soc2_cert_sections)
    associate_task_to_program(program, [task])
    result = refresh_organization_cache.delay(graphql_organization.id, action='DELETE')
    assert result.get()['success'] is True


@pytest.mark.django_db
@patch('program.utils.program_progress.get_subtasks_progress')
def test_get_unlocked_subtasks_for_archived_unlocked_org_certs(
    get_subtasks_progress_mocked,
    program,
    _subtasks,
    graphql_organization,
    _archived_unlocked_org_certification,
):
    _, subtask_2 = _subtasks
    get_program_progress(program, SubTask, no_cache=True)

    # This asserts verifies that the get_subtasks_progress function was called
    # inside get_program_progress with second param as queryset returning
    # the subtask_2 which is the subtask that should be unlocked for this
    # archived unlocked certs
    assert (
        get_subtasks_progress_mocked.call_args[ARGS][UNLOCKED_SUBTASKS_ARG].count() == 1
    )
    assert (
        get_subtasks_progress_mocked.call_args[ARGS][UNLOCKED_SUBTASKS_ARG].first().id
        == subtask_2.id
    )


@pytest.mark.django_db
@patch('program.utils.program_progress.get_subtasks_progress')
def test_get_unlocked_subtasks_for_unlocked_org_certs(
    get_subtasks_progress_mocked,
    program,
    _subtasks,
    graphql_organization,
    _unlocked_org_certification,
):
    subtask_1, _ = _subtasks
    get_program_progress(program, SubTask, no_cache=True)

    # This asserts verifies that the get_subtasks_progress function was called
    # inside get_program_progress with second param as queryset returning
    # the subtask_1 which is the subtask that should be unlocked for this
    # unlocked certs
    assert (
        get_subtasks_progress_mocked.call_args[ARGS][UNLOCKED_SUBTASKS_ARG].count() == 1
    )
    assert (
        get_subtasks_progress_mocked.call_args[ARGS][UNLOCKED_SUBTASKS_ARG].first().id
        == subtask_1.id
    )


@pytest.mark.django_db
def test_unlocked_and_archived_unlocked_certs(
    graphql_organization,
    _subtasks,
    _unlocked_org_certification,
    _archived_unlocked_org_certification,
):
    unlocked_and_archived_unlocked_certs = (
        graphql_organization.unlocked_and_archived_unlocked_certs
    )
    unlocked_and_archived_unlocked_certs_set = {
        unlocked_and_archived_unlocked_cert.id
        for unlocked_and_archived_unlocked_cert in unlocked_and_archived_unlocked_certs
    }

    assert unlocked_and_archived_unlocked_certs_set == {
        _unlocked_org_certification.id,
        _archived_unlocked_org_certification.id,
    }


@pytest.mark.django_db
def test_unlocked_subtasks(
    graphql_organization,
    task,
    _subtasks,
    _unlocked_org_certification,
    _archived_unlocked_org_certification,
):
    subtask_1, subtask_2 = _subtasks
    unlocked_subtasks = task.get_unlocked_subtasks(no_cache=True)
    unlocked_subtasks_set = {
        unlocked_subtask.id for unlocked_subtask in unlocked_subtasks
    }

    assert unlocked_subtasks_set == {subtask_1.id, subtask_2.id}
