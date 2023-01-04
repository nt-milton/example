import pytest
from django.db import connection

from monitor.laikaql.audit import build_query
from organization.tests import create_organization


@pytest.mark.functional
def test_get_query_builder_by_alias_for_audit():
    organization = create_organization(name='Test')
    audit_query = build_query(organization)
    expected_query = f'''
    select
        au.id as audit_id,
        au.name,
        au.audit_type as type,
        au.completed_at,
        (select concat(uu.first_name, ' ', uu.last_name)
        from user_user as uu
        where uu.id = aa.auditor_id) as auditor,
        a.name as firm,
        au.created_at as created_on,
        au.updated_at as last_updated
    from audit_audit as au
    left join audit_auditauditor aa on au.id = aa.audit_id
    left join audit_auditfirm a on au.audit_firm_id = a.id
    where au.organization_id = '{organization.id}'
    '''
    assert expected_query == audit_query


@pytest.mark.functional
def test_database_consistency_for_audits():
    with connection.cursor() as cursor:
        queries = [
            'select first_name, last_name from user_user',
            '''
            select
                au.name,
                au.audit_type as type,
                au.completed_at,
                au.created_at as created_on,
                au.updated_at as last_updated
            from audit_audit as au
            ''',
            'select auditor_id from audit_auditauditor',
            'select name from audit_auditfirm',
        ]
        for query in queries:
            cursor.execute(query)
