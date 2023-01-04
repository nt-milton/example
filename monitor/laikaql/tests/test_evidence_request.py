import pytest
from django.db import connection

from monitor.laikaql.evidence_request import build_query
from organization.tests import create_organization


@pytest.mark.functional
def test_get_query_builder_by_alias_for_evidence_request():
    organization = create_organization(name='Test')
    evidence_request_query = build_query(organization)
    expected_query = f'''
    select
        fe.id as evidence_request_id,
        fe.display_id as id,
        fe.name as evidence_name,
        fe.instructions,
        fe.status,
        fe.read,
        (select first_name from user_user as uu
         where uu.id = fe.assignee_id) as assignee,
        au.name as audit,
        fe.is_laika_reviewed as laika_reviewed,
        fe.is_deleted,
        fe.description,
        array (
            select fr.name
            from fieldwork_requirementevidence as fre
            left join fieldwork_requirement as fr on
            fr.id=fre.requirement_id
            where fre.evidence_id=fe.id
        ) as requiements,
        array (
            select fa.name from fieldwork_attachment as fa
            where fa.evidence_id = fa.id
        ) as attachments,
        fe.created_at as created_on,
        fe.updated_at as last_updated
    from fieldwork_evidence as fe
    left join audit_audit as au
    on au.id = fe.audit_id
    where au.organization_id = '{organization.id}'
    '''
    assert expected_query == evidence_request_query


@pytest.mark.functional
def test_database_consistency_for_evidence_request():
    with connection.cursor() as cursor:
        queries = [
            '''
            select first_name, last_name
            from user_user
            ''',
            '''
            select
                fe.display_id,
                fe.name,
                fe.instructions,
                fe.status,
                fe.read,
                fe.assignee_id,
                fe.is_laika_reviewed,
                fe.is_deleted,
                fe.description,
                fe.created_at,
                fe.updated_at
            from fieldwork_evidence as fe
            ''',
            '''
            select name from audit_audit
            ''',
            '''
            select requirement_id, evidence_id
            from fieldwork_requirementevidence as fre
            ''',
            '''
            select name from fieldwork_attachment
            ''',
        ]
        for query in queries:
            cursor.execute(query)
