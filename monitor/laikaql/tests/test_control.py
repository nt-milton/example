import pytest
from django.db import connection

from monitor.laikaql.control import build_query
from organization.tests import create_organization


@pytest.mark.functional
def test_get_query_builder_by_alias_for_control():
    organization = create_organization(name='Test')
    control_query = build_query(organization)
    expected_query = f'''
    select
    cc.id as control_id,
    cc.display_id as id,
    cc.name,
    cc.status,
    (select first_name from user_user as uu
     where uu.id = cc.owner1_id)  as owner,
    (select first_name from user_user as uu
     where uu.id = cc.approver_id) as approver,
    (select first_name from user_user as uu
     where uu.id = cc.administrator_id) as administrator,
    cc.category,
    cc.frequency,
    cc.updated_at,
    array (
        select t.name
        from control_controltag as ct
        left join tag_tag as t on
        t.id=ct.tag_id
        where ct.control_id=cc.id
    ) as tags
    from control_control cc
    where cc.organization_id='{organization.id}'
    '''
    assert expected_query == control_query


@pytest.mark.functional
def test_database_consistency_for_controls():
    with connection.cursor() as cursor:
        queries = [
            '''
            select id, name, status,
            owner1_id, category, updated_at
            from control_control
            ''',
            'select id, name from tag_tag',
            'select first_name from user_user',
        ]
        for query in queries:
            cursor.execute(query)
