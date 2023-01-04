import pytest
from django.core.exceptions import ValidationError

from monitor.result import TRIGGERED
from monitor.template import TEMPLATE_PREFIX, build_fix_links, build_query_for_variables
from monitor.tests.factory import create_monitor_result
from monitor.validators import (
    ALLOWED_INTERNAL_ROUTES,
    validate_fix_me_link,
    verify_internal_link,
)


@pytest.mark.parametrize("fix_me_link", ALLOWED_INTERNAL_ROUTES)
def test_verify_internal_link(fix_me_link):
    assert verify_internal_link(f'/{fix_me_link}') is None


@pytest.mark.parametrize(
    'fix_me_link, suggestion',
    [
        ('polici', 'policies'),
        ('mntor', 'monitors'),
        ('dcmens', 'documents'),
        ('orgnzatn', 'organization'),
        ('dtroms', 'datarooms'),
        ('riptors', 'reports'),
        ('aurts', 'audits'),
        ('tranng', 'training'),
        ('ctrls', 'controls'),
        ('pple', 'people'),
    ],
)
def test_verify_internal_link_suggestion(fix_me_link, suggestion):
    with pytest.raises(
        ValidationError,
        match=f'{fix_me_link} is not a valid link. Did you mean {suggestion}?',
    ):
        verify_internal_link(f'/{fix_me_link}')


@pytest.mark.parametrize('fix_me_link', ['', 'a', 'afg'])
def test_verify_internal_link_no_suggestion(fix_me_link):
    with pytest.raises(
        ValidationError, match=f'{fix_me_link} is not a valid internal link'
    ):
        verify_internal_link(f'/{fix_me_link}')


@pytest.mark.parametrize(
    'fix_me_link',
    [
        '/monitors/$LO_Users.Id',
        '/lob/pull_request?objectId=$lo_pull_requests.key',
    ],
)
def test_validate_link_case_insensitive_no_exception(fix_me_link):
    validate_fix_me_link(fix_me_link)


@pytest.mark.functional
def test_fixme_no_match_query_exception():
    with pytest.raises(ValidationError, match='Placeholder tables do not match query'):
        validate_fix_me_link(
            '/lob/default?objectId=$people.people_id', 'select * from lo_users'
        )


def test_fixme_match_query_no_exception():
    validate_fix_me_link('/people?userId=$lo_users.id', 'select * from lo_users')


def test_select_domain_fixme():
    query = 'select name from people'
    new_query = build_query_for_variables(query, 'http://www.$people.people_id.com', '')

    expected_alias = f'{TEMPLATE_PREFIX}_people__people_id'
    expected = f'select name, people.people_id as {expected_alias} from people'
    assert new_query == expected


@pytest.mark.functional
def test_case_placeholders_domain():
    placeholder = 'test123'
    result = create_monitor_result(
        status=TRIGGERED,
        result={'data': ['record_1'], 'variables': [{'people.people_id': placeholder}]},
    )
    fix_me_link = 'https://www.$people.people_id.com'
    result.organization_monitor.monitor.fix_me_link = fix_me_link
    links = build_fix_links(result.organization_monitor, result.result)

    assert links == [f'https://www.{placeholder}.com']


@pytest.mark.functional
@pytest.mark.parametrize(
    'fix_me_link',
    [
        'http://www.$people.people_id.com',
        'http://www.example.com',
        'http://www.example.com/$people.people_id',
        'http://www.$people.people_id.com/$people.people_id',
    ],
)
def test_place_holder_in_domain_name(fix_me_link):
    validate_fix_me_link(fix_me_link)
