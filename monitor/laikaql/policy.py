from organization.models import Organization


def build_query(organization: Organization) -> str:
    return f'''
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


def build_query_test(organization: Organization) -> str:
    return f'''
    select
    p.created_at,
    p.updated_at,
    p.display_id,
    p.name,
    p.description,
    p.is_published,
    p.category,
    p.policy_text,
    p.is_visible_in_dataroom
    from policy_policy as p
    where p.organization_id='{organization.id}'
    '''
