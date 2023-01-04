from objects.system_types import BackgroundCheck
from user.models import User

VETTY_SYSTEM = 'Vetty'
NOT_APPLICABLE = 'N/A'


def map_vetty_background_checks_response(
    background_check, connection_name, source_system
):
    applicant = background_check.get('applicant', {})
    package_name = background_check.get('package', {}).get('name', '')
    laika_person = User.objects.filter(email=applicant.get('email')).first()
    people_id = None
    if laika_person:
        people_id = str(
            laika_person.username
            if laika_person.is_active and laika_person.username
            else laika_person.id
        )
    lo_background_check = BackgroundCheck()
    lo_background_check.id = background_check.get('id')
    lo_background_check.first_name = applicant.get('first_name', '')
    lo_background_check.last_name = applicant.get('last_name', '')
    lo_background_check.email = applicant.get('email', '')
    lo_background_check.check_name = package_name
    lo_background_check.status = background_check.get('status', '')
    lo_background_check.estimated_completion_date = None
    lo_background_check.initiation_date = None
    lo_background_check.package = package_name
    lo_background_check.link_people_table = people_id
    lo_background_check.source_system = source_system
    lo_background_check.connection_name = connection_name
    return lo_background_check.data()


def _map_background_checks(response, connection_name):
    return map_vetty_background_checks_response(response, connection_name, VETTY_SYSTEM)
