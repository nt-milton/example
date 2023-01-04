import pytest
from django.db import connection

from monitor.laikaql.policy import build_query
from organization.tests import create_organization


@pytest.mark.functional
def test_get_query_builder_by_alias_for_policy():
    organization = create_organization(name='Test')
    policy_query = build_query(organization)
    expected_query = f'''
    select
    p.id as policy_id,
    p.created_at,
    p.updated_at,
    p.display_id,
    p.name,
    p.description,
    p.is_published,
    p.category,
    p.policy_text,
    p.is_visible_in_dataroom,
    pp.version as version,
    pp.created_at as publication_date,
    owners.email as owner,
    approvers.email as approver,
    administrators.email as administrator,
    array (
        select t.name
        from policy_policytag as pt
        left join tag_tag as t on
        t.id=pt.tag_id
        where pt.policy_id=p.id
    ) as tags
    from policy_policy as p
    left join user_user as owners on
    p.owner_id=owners.id
    left join user_user as approvers on
    p.approver_id=approvers.id
    left join user_user as administrators on
    p.administrator_id=administrators.id
    left join policy_publishedpolicy as pp on
    pp.version = (
        select max(pp.version)
        from policy_publishedpolicy as pp
        where pp.policy_id=p.id
    ) and pp.policy_id=p.id
    where p.organization_id='{organization.id}'
    '''
    assert expected_query == policy_query


@pytest.mark.functional
def test_database_consistency_for_policies():
    with connection.cursor() as cursor:
        queries = [
            '''
            select created_at, updated_at, display_id, name, description,
            is_published, category, policy_text, is_visible_in_dataroom,
            owner_id, approver_id, administrator_id, organization_id
            from policy_policy
            ''',
            '''
            select version, created_at, policy_id from policy_publishedpolicy
            ''',
            'select id, email from user_user',
            'select id, name from tag_tag',
            'select tag_id, policy_id from policy_policytag',
        ]
        for query in queries:
            cursor.execute(query)
