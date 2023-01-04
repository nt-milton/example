from organization.models import Organization


def build_query(organization: Organization) -> str:
    return f'''
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
