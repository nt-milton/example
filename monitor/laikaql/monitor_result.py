from organization.models import Organization

LIMIT_RESULT_SIZE = 1000000
LIMIT_RESULT_MESSAGE = 'Too large to be shown'


def build_query(organization: Organization) -> str:
    return f'''
    select
    mr.id as monitor_result_id,
    mr.created_at,
    mr.query,
    mr.status,
    CASE
        WHEN LENGTH(CAST(mr.result AS TEXT)) > {LIMIT_RESULT_SIZE}
            THEN '{LIMIT_RESULT_MESSAGE}'
        ELSE CAST(mr.result AS TEXT)
    END as result,
    m.name as monitor
    from monitor_monitorresult as mr
    left join monitor_organizationmonitor as om
    on om.id = mr.organization_monitor_id
    left join monitor_monitor as m
    on m.id = om.monitor_id
    where om.organization_id='{organization.id}'
    '''
