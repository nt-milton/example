from organization.models import Organization


def build_query(organization: Organization) -> str:
    return f'''
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
