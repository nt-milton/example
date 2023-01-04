from typing import Dict

from objects.system_types import BackgroundCheck

CHECKR_SYSTEM = 'checkr'


def map_background_checks(check, connection_name):
    lo_check = BackgroundCheck()
    lo_check.id = check.get('id')
    lo_check.check_name = check.get('package')
    lo_check.status = check.get('status')
    lo_check.people_status = check.get('people_status')
    user: Dict = check.get('user') or {}
    lo_check.first_name = user.get('first_name')
    lo_check.last_name = user.get('last_name')
    lo_check.email = user.get('email')
    lo_check.source_system = CHECKR_SYSTEM
    lo_check.connection_name = connection_name
    lo_check.estimated_completion_date = check.get('estimated_completion_date')
    lo_check.initiation_date = check.get('initiation_date')
    lo_check.link_people_table = check.get('link_people_table')
    lo_check.package = check.get('package')

    return lo_check.data()
