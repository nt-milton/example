from datetime import datetime

import pytest

from auditor.tests.test_utils import get_requirement_first_test
from fieldwork.constants import CHECKLIST_AUTOMATED_TESTING_SEPARATOR
from fieldwork.models import Evidence, Requirement, Test
from user.constants import AUDITOR

from .mutations import (
    AUTOMATE_AUDITOR_REQUIREMENT_TEST,
    CREATE_AUDITOR_REQUIREMENT_TEST,
    DELETE_AUDITOR_REQUIREMENT_TEST,
    UPDATE_AUDITOR_REQUIREMENT_TEST,
)


@pytest.mark.functional(permissions=['fieldwork.delete_test'])
def test_delete_auditor_requirement_test(graphql_audit_client, requirement_with_test):
    test = get_requirement_first_test(requirement_with_test)
    graphql_audit_client.execute(
        DELETE_AUDITOR_REQUIREMENT_TEST, variables={'testId': test.id}
    )
    soft_deleted_test = Test.objects.get(id=test.id)
    assert soft_deleted_test.is_deleted


@pytest.mark.functional(permissions=['fieldwork.delete_test'])
def test_delete_auditor_requirement_test_with_not_found_test_id(
    graphql_audit_client,
):
    response = graphql_audit_client.execute(
        DELETE_AUDITOR_REQUIREMENT_TEST, variables={'testId': 999}
    )
    error = response['errors'][0]
    assert error['message'] == 'Not found'


@pytest.mark.functional(permissions=['fieldwork.delete_test'])
def test_delete_auditor_requirement_test_with_auditor_user(
    graphql_audit_client, graphql_audit_user
):
    graphql_audit_user.role = AUDITOR
    graphql_audit_user.save()
    response = graphql_audit_client.execute(
        DELETE_AUDITOR_REQUIREMENT_TEST, variables={'testId': 1}
    )
    error = response['errors'][0]
    assert error['message'] == 'Only auditor admin can delete tests'


@pytest.mark.functional(permissions=['fieldwork.add_test'])
def test_create_auditor_requirement_test(graphql_audit_client, requirement_with_test):
    response = graphql_audit_client.execute(
        CREATE_AUDITOR_REQUIREMENT_TEST,
        variables={
            'input': dict(
                requirementId=str(requirement_with_test.id),
                auditId=str(requirement_with_test.audit.id),
            )
        },
    )
    data = response['data']
    test = data['createAuditorRequirementTest']['test']
    assert test['displayId'] == 'Test-4'


@pytest.mark.functional(permissions=['fieldwork.add_test'])
def test_create_auditor_requirement_first_test(graphql_audit_client, requirement):
    response = graphql_audit_client.execute(
        CREATE_AUDITOR_REQUIREMENT_TEST,
        variables={
            'input': dict(
                requirementId=str(requirement.id), auditId=str(requirement.audit.id)
            )
        },
    )
    data = response['data']
    test = data['createAuditorRequirementTest']['test']
    assert test['displayId'] == 'Test-1'


@pytest.mark.functional(permissions=['fieldwork.change_test'])
def test_automate_auditor_requirement_test(
    graphql_audit_client,
    requirement_with_test: Requirement,
    not_tested_test: Test,
    evidence_with_monitor_attachments: Evidence,
):
    assert not_tested_test.automated_test_result is None
    response = graphql_audit_client.execute(
        AUTOMATE_AUDITOR_REQUIREMENT_TEST,
        variables={
            'input': dict(
                testId=str(not_tested_test.id),
                requirementId=str(requirement_with_test.id),
                auditId=str(requirement_with_test.audit.id),
            )
        },
    )
    updated_test = Test.objects.get(id=not_tested_test.id)
    response_test = response['data']['automateAuditorRequirementTest']['test']
    assert response_test['displayId'] == updated_test.display_id
    assert CHECKLIST_AUTOMATED_TESTING_SEPARATOR in response_test['automatedChecklist']
    assert updated_test.automated_test_result is not None
    assert updated_test.times_run_automate_test == 1
    assert updated_test.automated_test_result_updated_at.strftime(
        "%Y/%m/%d"
    ) == datetime.now().strftime("%Y/%m/%d")


@pytest.mark.functional(permissions=['fieldwork.change_test'])
def test_automate_auditor_requirement_test_with_past_automation(
    graphql_audit_client,
    requirement_with_test: Requirement,
    not_tested_test: Test,
    evidence_with_monitor_attachments: Evidence,
):
    past_automation_content = '<p>This is the past automation</p>'
    not_tested_test.automated_test_result = past_automation_content
    not_tested_test.times_run_automate_test = 1
    not_tested_test.save()

    response = graphql_audit_client.execute(
        AUTOMATE_AUDITOR_REQUIREMENT_TEST,
        variables={
            'input': dict(
                testId=str(not_tested_test.id),
                requirementId=str(requirement_with_test.id),
                auditId=str(requirement_with_test.audit.id),
            )
        },
    )
    updated_test = Test.objects.get(id=not_tested_test.id)
    response_test = response['data']['automateAuditorRequirementTest']['test']
    assert response_test['displayId'] == updated_test.display_id
    assert CHECKLIST_AUTOMATED_TESTING_SEPARATOR in response_test['automatedChecklist']
    assert past_automation_content in response_test['automatedChecklist']
    assert updated_test.times_run_automate_test == 2
    assert updated_test.automated_test_result_updated_at.strftime(
        "%Y/%m/%d"
    ) == datetime.now().strftime("%Y/%m/%d")


@pytest.mark.functional(permissions=['fieldwork.change_test'])
def test_automate_auditor_requirement_test_with_not_automatable_test(
    graphql_audit_client, requirement_with_test: Requirement, not_tested_test: Test
):
    response = graphql_audit_client.execute(
        AUTOMATE_AUDITOR_REQUIREMENT_TEST,
        variables={
            'input': dict(
                testId=str(not_tested_test.id),
                requirementId=str(requirement_with_test.id),
                auditId=str(requirement_with_test.audit.id),
            )
        },
    )
    error = response['errors'][0]['message']
    assert error == 'Test cannot be automated'


@pytest.mark.functional(permissions=['fieldwork.change_test'])
def test_update_auditor_requirement_test_field(
    graphql_audit_client,
    graphql_audit_user,
    requirement_with_test,
    exceptions_noted_test,
):
    result = 'not_tested'

    assert exceptions_noted_test.last_edited_by is None
    assert exceptions_noted_test.last_edited_at is None

    graphql_audit_client.execute(
        UPDATE_AUDITOR_REQUIREMENT_TEST,
        variables={
            'input': dict(
                auditId=requirement_with_test.audit.id,
                requirementId=str(requirement_with_test.id),
                testId=str(exceptions_noted_test.id),
                field='result',
                value=result,
            )
        },
    )

    test = Test.objects.get(id=exceptions_noted_test.id)
    assert test.result == result
    assert test.last_edited_by is None
    assert test.last_edited_at is None


@pytest.mark.functional(permissions=['fieldwork.change_test'])
def test_update_auditor_requirement_test_name(
    graphql_audit_client, graphql_audit_user, requirement_with_test, not_tested_test
):
    name_text = 'XXXX'

    assert not_tested_test.last_edited_by is None
    assert not_tested_test.last_edited_at is None

    graphql_audit_client.execute(
        UPDATE_AUDITOR_REQUIREMENT_TEST,
        variables={
            'input': dict(
                auditId=requirement_with_test.audit.id,
                requirementId=str(requirement_with_test.id),
                testId=str(not_tested_test.id),
                field='name',
                value=name_text,
            )
        },
    )

    test = Test.objects.get(id=not_tested_test.id)
    assert test.name == name_text
    assert test.last_edited_by == graphql_audit_user
    assert test.last_edited_at.strftime("%Y/%m/%d") == datetime.now().strftime(
        "%Y/%m/%d"
    )


@pytest.mark.functional(permissions=['fieldwork.change_test'])
def test_update_auditor_requirement_test_result_null(
    graphql_audit_client, requirement_with_test, not_tested_test
):
    graphql_audit_client.execute(
        UPDATE_AUDITOR_REQUIREMENT_TEST,
        variables={
            'input': dict(
                auditId=requirement_with_test.audit.id,
                requirementId=str(requirement_with_test.id),
                testId=str(not_tested_test.id),
                field='result',
                value=None,
            )
        },
    )

    assert Test.objects.get(id=not_tested_test.id).result is None


@pytest.mark.functional(permissions=['fieldwork.change_test'])
def test_update_auditor_requirement_test_automated_checklist(
    graphql_audit_client, requirement_with_test, not_tested_test
):
    checklist_content = '<p>This is the content of checklist</p>'
    automated_result_content = '<p>This is automated result content</p>'

    graphql_audit_client.execute(
        UPDATE_AUDITOR_REQUIREMENT_TEST,
        variables={
            'input': dict(
                auditId=requirement_with_test.audit.id,
                requirementId=str(requirement_with_test.id),
                testId=str(not_tested_test.id),
                field='automated_checklist',
                value=f'''{checklist_content}
                {CHECKLIST_AUTOMATED_TESTING_SEPARATOR}
                {automated_result_content}''',
            )
        },
    )
    test = Test.objects.get(id=not_tested_test.id)
    assert checklist_content in test.checklist
    assert automated_result_content in test.automated_test_result


@pytest.mark.functional(permissions=['fieldwork.change_test'])
def test_update_auditor_requirement_test_automated_checklist_no_separator(
    graphql_audit_client, requirement_with_test, not_tested_test
):
    checklist_content = '<p>This is the content of checklist</p>'

    graphql_audit_client.execute(
        UPDATE_AUDITOR_REQUIREMENT_TEST,
        variables={
            'input': dict(
                auditId=requirement_with_test.audit.id,
                requirementId=str(requirement_with_test.id),
                testId=str(not_tested_test.id),
                field='automated_checklist',
                value=checklist_content,
            )
        },
    )
    test = Test.objects.get(id=not_tested_test.id)
    assert checklist_content in test.checklist
    assert test.automated_test_result == ''


@pytest.mark.functional(permissions=['fieldwork.change_test'])
def test_update_auditor_requirement_test_automated_checklist_no_automated_content(
    graphql_audit_client, requirement_with_test, not_tested_test
):
    checklist_content = '<p>This is the content of checklist</p>'

    graphql_audit_client.execute(
        UPDATE_AUDITOR_REQUIREMENT_TEST,
        variables={
            'input': dict(
                auditId=requirement_with_test.audit.id,
                requirementId=str(requirement_with_test.id),
                testId=str(not_tested_test.id),
                field='automated_checklist',
                value=f'{checklist_content}{CHECKLIST_AUTOMATED_TESTING_SEPARATOR}',
            )
        },
    )
    test = Test.objects.get(id=not_tested_test.id)
    assert checklist_content in test.checklist
    assert test.automated_test_result == ''
