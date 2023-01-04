from user.constants import ALL_HEADERS, ROLE_MEMBER
from user.models import (
    BACKGROUND_CHECK_STATUS,
    EMPLOYMENT_STATUS,
    EmploymentSubtype,
    EmploymentType,
    User,
)


def map_choices_to_dic_inverted(choices):
    return {value: key for key, value in choices}


def map_choices_to_dic(choices):
    return {key: value for key, value in choices}


def parse_user_from_excel(user_dic, organization):
    """
    Creates an object to save a new user. It uses a row from the excel.
    The role should be a valid value from USER_ROLES.
    """
    result = {}
    for header in ALL_HEADERS:
        value = user_dic.get(header.get('name'))
        result[header.get('key')] = value.strip() if isinstance(value, str) else value
    result['role'] = user_dic.get('Role')
    fields_options = [
        ('employment_type', map_choices_to_dic_inverted(EmploymentType.choices)),
        ('employment_subtype', map_choices_to_dic_inverted(EmploymentSubtype.choices)),
        (
            'background_check_status',
            map_choices_to_dic_inverted(BACKGROUND_CHECK_STATUS),
        ),
        ('employment_status', map_choices_to_dic_inverted(EMPLOYMENT_STATUS)),
    ]
    for key, options in fields_options:
        result[key] = options.get(result[key])
    result['manager_email'] = (
        result['manager_email'].lower() if result['manager_email'] else ''
    )
    result['email'] = result['email'].lower() if result['email'] else ''
    result['organization_id'] = organization.id
    return result


def parse_user_fields(organization, payload):
    manager_email = payload.get('manager_email')
    manager = None
    if manager_email:
        manager = User.objects.filter(
            email=manager_email, organization=organization
        ).first()
    return {
        'username': payload.get('username'),
        'email': payload.get('email'),
        'last_name': payload.get('last_name'),
        'first_name': payload.get('first_name'),
        'phone_number': payload.get('phone_number'),
        'title': payload.get('title'),
        'department': payload.get('department'),
        'employment_type': payload.get('employment_type'),
        'employment_subtype': payload.get('employment_subtype'),
        'start_date': payload.get('start_date'),
        'end_date': payload.get('end_date'),
        'employment_status': payload.get('employment_status', ''),
        'background_check_passed_on': payload.get('background_check_passed_on'),
        'background_check_status': payload.get('background_check_status', ''),
        'role': payload.get('role', ROLE_MEMBER),
        'manager': manager,
        'organization_id': organization.id,
    }


def sanitize_dict(data_object):
    for key in data_object:
        if isinstance(data_object[key], str):
            data_object[key] = data_object[key].strip()
    return data_object
