from organization.models import Organization


def build_query(organization: Organization) -> str:
    return f'''
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
