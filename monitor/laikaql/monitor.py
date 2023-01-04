from organization.models import Organization


def build_query(organization: Organization) -> str:
    return f'''
    select
    om.id as monitor_instance_id,
    m.id as monitor_id,
    m.name as name,
    m.description as description,
    m.query as query,
    m.health_condition as health_condition,
    m.monitor_type as monitor_type,
    m.frequency as frequency,
    om.active as active,
    om.status as status,
    mr.created_at as last_run,
    string_to_array(
        regexp_replace(
            m.tag_references, E'[\\n\\r]+', ',', 'g'
        ),
        ','
    ) as tags,
    string_to_array(
        regexp_replace(
            m.control_references, E'[\\n\\r]+', ',', 'g'
        ),
        ','
    ) as controls
    from monitor_organizationmonitor as om
    left join monitor_monitor as m
    on m.id = om.monitor_id
    left join monitor_monitorresult as mr
    on mr.created_at = (
        select max(mr.created_at)
        from monitor_monitorresult as mr
        where mr.organization_monitor_id = om.id
    )
    where om.organization_id = '{organization.id}'
    '''
