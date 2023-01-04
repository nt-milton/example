import pytest
from django.db import connection

from monitor.laikaql.document import build_query
from organization.tests import create_organization


@pytest.mark.functional
def test_get_query_builder_by_alias_for_documents():
    organization = create_organization(name='Test')
    document_query = build_query(organization)
    expected_query = f'''
    select
    e.id as document_id,
    concat(uu.first_name,' ', uu.last_name) as owner,
    e.type,
    e.name,
    array_agg(tt.name) as tags,
    e.created_at as created_on,
    e.updated_at as last_updated
    from evidence_evidence e
    left join drive_driveevidence de on e.id=de.evidence_id
    left join user_user uu on de.owner_id = uu.id
    left join evidence_tagevidence et on e.id = et.evidence_id
    left join tag_tag tt on tt.id = et.tag_id
    where e.organization_id='{organization.id}' and de.is_template=false
    group by e.id, uu.first_name, uu.last_name
    '''
    assert expected_query == document_query


@pytest.mark.functional
def test_database_consistency_for_documents():
    with connection.cursor() as cursor:
        queries = [
            '''
            select first_name, last_name
            from user_user
            ''',
            '''
            select
                tag_id,
                evidence_id
            from evidence_tagevidence
            ''',
            'select id, name from tag_tag',
            '''
            select
                created_at,
                updated_at,
                name,
                type,
                organization_id
            from evidence_evidence
            ''',
            '''
            select
                is_template,
                evidence_id
            from drive_driveevidence
            ''',
        ]
        for query in queries:
            cursor.execute(query)
