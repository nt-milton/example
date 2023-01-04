import pytest
from django.db import connection

from monitor.laikaql.people import build_query
from organization.tests import create_organization
from user.tests import create_user


@pytest.mark.functional
def test_query_built_for_user():
    organization = create_organization(name='Test')
    create_user(organization)
    organization.id = str(organization.id).replace('-', '')
    people_query = build_query(organization)
    with connection.cursor() as cursor:
        cursor.execute(people_query)
        columns = [col[0] for col in cursor.description]
        data = cursor.fetchall()
        assert columns == COLUMNS_FOR_PEOPLE
        assert len(data) > 0


@pytest.mark.functional
def test_get_query_builder_by_alias_for_people():
    organization = create_organization(name='Test')
    people_query = build_query(organization)
    expected_query = f'''
    select
    u.id as people_id,
    u.username,
    u.first_name,
    u.last_name,
    u.email,
    u.is_active,
    u.date_joined,
    u.role,
    u.department,
    u.employment_status,
    u.employment_subtype,
    u.employment_type,
    u.end_date,
    u.phone_number,
    u.start_date,
    u.title,
    u.discovery_state,
    u.mfa,
    manager.email as manager
    from user_user as u
    left join user_user as manager on
    u.manager_id=manager.id
    where u.organization_id='{organization.id}'
    '''
    assert expected_query == people_query


COLUMNS_FOR_PEOPLE = [
    'people_id',
    'username',
    'first_name',
    'last_name',
    'email',
    'is_active',
    'date_joined',
    'role',
    'department',
    'employment_status',
    'employment_subtype',
    'employment_type',
    'end_date',
    'phone_number',
    'start_date',
    'title',
    'discovery_state',
    'mfa',
    'manager',
]
