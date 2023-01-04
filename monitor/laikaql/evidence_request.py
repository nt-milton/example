from organization.models import Organization


def build_query(organization: Organization) -> str:
    return f'''
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
