from unittest.mock import patch

import pytest
from django.db.models import TextField
from django.db.models.functions import Cast

from audit.models import AuditAuditor
from auditor.utils import (
    get_next_display_id,
    get_requirement_tests,
    increment_display_id,
    validate_requirement_complete_status_change,
)
from fieldwork.models import Requirement, Test
from laika.utils.exceptions import ServiceException
from user.constants import AUDITOR, AUDITOR_ADMIN
from user.tests.factory import create_user_auditor


@pytest.fixture
def user_auditor(role, has_firm):
    return create_user_auditor(
        email='johndoe@heylaika.com',
        role=role,
        with_audit_firm=has_firm,
    )


@pytest.fixture
def test(requirement):
    return Test.objects.create(
        display_id='Test-1', requirement=requirement, result='not_tested'
    )


@pytest.fixture
def test_with_param(result, is_deleted, notes, requirement):
    return Test.objects.create(
        display_id='Test-1',
        requirement=requirement,
        result=result,
        is_deleted=is_deleted,
        notes=notes,
    )


@pytest.fixture
def audit_auditor(title, requirement, user_auditor):
    return AuditAuditor.objects.create(
        audit=requirement.audit, auditor=user_auditor, title_role=title
    )


def get_requirement_first_test(requirement):
    requirement_tests = Test.objects.filter(requirement=requirement)
    return requirement_tests.first()


@pytest.mark.functional
def test_increment_display_id(requirement):
    audit_id = str(requirement.audit.id)
    incremental_display_id = increment_display_id(
        Requirement, audit_id=audit_id, reference='LCL'
    )

    assert incremental_display_id == 'LCL-2'


@pytest.mark.functional
def test_get_display_id_first_id(requirement):
    tests = Test.objects.filter(requirement_id=str(requirement.id))
    display_id = get_next_display_id(tests, 'Test')

    assert display_id == 'Test-1'


@pytest.mark.functional
def test_get_display_id_sequence(requirement):
    Test.objects.create(display_id='Test-1', requirement=requirement)
    tests = Test.objects.filter(requirement_id=str(requirement.id))
    display_id = get_next_display_id(tests, 'Test')

    assert display_id == 'Test-2'


NOT_ASSOCIATED_TO_AUDIT_FIRM_MSG = '''
            Requirements can only be marked as complete
            by a member of the Audit Firm
            '''
USER_IS_NOT_ADMIN_MSG = '''
                Requirements can only be marked as complete by a
                Reviewer, Lead Auditor or Admin
                '''
WITHOUT_NOTES_MSG = '''LCL-1:
            Tests with Exceptions Noted or Not Tested must have notes'''


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role, has_firm, expected_msg",
    [
        (AUDITOR_ADMIN, False, NOT_ASSOCIATED_TO_AUDIT_FIRM_MSG),
        (AUDITOR, True, USER_IS_NOT_ADMIN_MSG),
        (AUDITOR_ADMIN, True, WITHOUT_NOTES_MSG),
    ],
)
def test_validate_requirement_complete_status_change_should_raise_errors(
    user_auditor, requirement, expected_msg, test
):
    with pytest.raises(ServiceException) as exception_info:
        validate_requirement_complete_status_change(
            user_auditor.user, requirement.audit, [requirement.id]
        )

    assert str(exception_info.value) == expected_msg


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role, has_firm, result, is_deleted, notes, title",
    [
        (AUDITOR_ADMIN, True, 'not_tested', True, '', ''),
        (AUDITOR_ADMIN, True, 'exceptions_noted', True, '', ''),
        (AUDITOR_ADMIN, True, 'not_tested', False, 'With Notes', ''),
        (AUDITOR_ADMIN, True, 'no_exceptions_noted', False, '', ''),
        (AUDITOR, True, 'no_exceptions_noted', False, 'With notes', 'lead_auditor'),
        (AUDITOR, True, 'not_tested', True, '', 'reviewer'),
    ],
)
def test_validate_requirement_complete_status_change_pass(
    user_auditor, requirement, test_with_param, audit_auditor
):
    success = validate_requirement_complete_status_change(
        user_auditor.user, requirement.audit, [requirement.id]
    )

    assert success


@pytest.mark.django_db
@patch(
    'auditor.utils.get_display_id_order_annotation',
    return_value=Cast('display_id', output_field=TextField()),
)
def test_get_requirement_tests(get_display_id_order_annotation_mock, requirement, test):
    tests = get_requirement_tests(requirement)

    assert len(tests) == 1
    get_display_id_order_annotation_mock.assert_called()
