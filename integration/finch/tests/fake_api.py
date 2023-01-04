import json
from pathlib import Path

from httmock import HTTMock
from httmock import response as mock_response
from httmock import urlmatch

TEST_COMPANY = 'Testing Laika'
TEST_LOCATION = {
    'line1': '335 S 560 W',
    'line2': '',
    'city': 'Lindon',
    'state': 'UT',
    'country': 'US',
    'postal_code': '84042',
}
TEST_LOCATION_2 = {
    'line1': None,
    'line2': '',
    'city': 'New York',
    'state': 'NY',
    'country': 'US',
    'postal_code': '83452',
}
LAST_NAME = 'Chacon'
FIRST_NAME = 'Danny'
DEPARTMENT_NAME = 'Development'
TEST_INDIVIDUAL = {
    'id': '7045b408-2043-4d57-91b5-87b11b22baae',
    'first_name': FIRST_NAME,
    'last_name': LAST_NAME,
    'middle_name': "Joel",
    'department': {'name': DEPARTMENT_NAME},
    'manager': {'id': '23418f35-694b-4908-8d74-727e96c177eb'},
    'is_active': True,
}
TEST_MANAGER = {
    'id': '23418f35-694b-4908-8d74-727e96c177eb',
    'first_name': 'Ronald',
    'last_name': 'Z.',
    'manager': None,
    'department': {'name': DEPARTMENT_NAME},
    'is_active': True,
}
TEST_INDIVIDUAL_WITHOUT_EMAILS = {
    'id': '23418f35-694b-4908-8d74-727e96c177oz',
    'first_name': 'Otto',
    'last_name': 'Zuniga',
    'manager': {'id': '23418f35-694b-4908-8d74-727e96c177eb'},
    'department': {'name': DEPARTMENT_NAME},
    'is_active': True,
}
TEST_INDIVIDUAL_WITHOUT_EMAILS_NEITHER_MANAGER = {
    'id': '23418f35-694b-4908-8d74-727e96c177ts',
    'first_name': 'Taj',
    'last_name': 'Sangha',
    'manager': None,
    'department': {'name': DEPARTMENT_NAME},
    'is_active': False,
}
INTEGRATIONS_PAVE_USER = {
    'id': '58234f35-694b-4908-8d74-727e96c345df',
    'first_name': 'integrations',
    'last_name': 'pave',
    'manager': None,
    'department': None,
    'is_active': False,
}
USER_WITH_MANAGER_THAT_DONT_HAVE_EMAIL = {
    'id': '58234f35-694b-4908-8d74-727e96c344rf',
    'first_name': 'James',
    'last_name': 'Fletcher',
    # this manager doesn't have an email
    'manager': {'id': '23418f35-694b-4908-8d74-727e96c177ts'},
    'department': None,
    'is_active': True,
}
ONLY_PERSONAL_EMAIL_INDIVIDUAL = {
    'id': '23418f35-694b-4908-8d74-727e96c175nm',
    'first_name': 'Email',
    'last_name': 'Personal Only',
    'manager': None,
    'department': {'name': DEPARTMENT_NAME},
    'is_active': True,
}
INDIVIDUAL_WITH_ONLY_PERSONAL_PHONE = {
    'id': '23418f35-694b-4908-8d74-727e96c179op',
    'first_name': 'Phone',
    'last_name': 'Personal Only',
    'manager': None,
    'department': {'name': DEPARTMENT_NAME},
    'is_active': True,
}
TEST_INDIVIDUAL_WITHOUT_PHONES = {
    'id': '23418f35-694b-4908-8d74-727e96c171lk',
    'first_name': 'NoPhones',
    'last_name': 'User',
    'manager': {'id': '23418f35-694b-4908-8d74-727e96c177eb'},
    'department': {'name': DEPARTMENT_NAME},
    'is_active': True,
}
PHONE_NUMBER = '801-724-6600'


def fake_finch_api():
    """This fake will intercept http calls to google domain and
    It will use a fake implementation"""
    return HTTMock(
        fake_company,
        fake_directory,
        fake_individual,
        fake_employment,
        fake_access_token,
    )


def fake_finch_api_without_employment_type():
    """This fake will intercept http calls to google domain and
    It will use a fake implementation"""
    return HTTMock(
        fake_company,
        fake_directory,
        fake_individual,
        fake_employment_without_type,
        fake_access_token,
    )


def fake_failed_finch_api():
    return HTTMock(fake_access_token, call_fail_company)


@urlmatch(netloc='api.tryfinch.com', path='/employer/company')
def fake_company(url, request):
    return create_company_response()


@urlmatch(netloc='api.tryfinch.com', path='/auth/token')
def fake_access_token(url, request):
    return create_access_token_response()


@urlmatch(netloc='api.tryfinch.com', path='/employer/directory')
def fake_directory(url, request):
    return json.dumps(
        {
            'individuals': [
                TEST_INDIVIDUAL,
                TEST_MANAGER,
                TEST_INDIVIDUAL_WITHOUT_EMAILS,
                TEST_INDIVIDUAL_WITHOUT_EMAILS_NEITHER_MANAGER,
                INTEGRATIONS_PAVE_USER,
                USER_WITH_MANAGER_THAT_DONT_HAVE_EMAIL,
                ONLY_PERSONAL_EMAIL_INDIVIDUAL,
                INDIVIDUAL_WITH_ONLY_PERSONAL_PHONE,
                TEST_INDIVIDUAL_WITHOUT_PHONES,
            ]
        }
    )


@urlmatch(netloc='api.tryfinch.com', path='/employer/individual')
def fake_individual(url, request):
    return json.dumps(
        {
            'responses': [
                create_detail(TEST_INDIVIDUAL),
                create_detail(TEST_MANAGER),
                create_detail(TEST_INDIVIDUAL_WITHOUT_EMAILS, with_emails=False),
                create_detail(
                    TEST_INDIVIDUAL_WITHOUT_EMAILS_NEITHER_MANAGER, with_emails=False
                ),
                create_detail(INTEGRATIONS_PAVE_USER),
                create_detail(USER_WITH_MANAGER_THAT_DONT_HAVE_EMAIL),
                create_detail(ONLY_PERSONAL_EMAIL_INDIVIDUAL, only_personal_email=True),
                create_detail(
                    INDIVIDUAL_WITH_ONLY_PERSONAL_PHONE, only_personal_phone=True
                ),
                create_detail(TEST_INDIVIDUAL_WITHOUT_PHONES, with_phones=False),
            ]
        }
    )


@urlmatch(netloc='api.tryfinch.com', path='/employer/employment')
def fake_employment(url, request):
    return json.dumps(
        {
            'responses': [
                create_employment(TEST_INDIVIDUAL),
                create_employment(TEST_MANAGER),
                create_employment(TEST_INDIVIDUAL_WITHOUT_EMAILS),
                create_employment(TEST_INDIVIDUAL_WITHOUT_EMAILS_NEITHER_MANAGER),
                create_employment(INTEGRATIONS_PAVE_USER),
                create_employment(USER_WITH_MANAGER_THAT_DONT_HAVE_EMAIL),
                create_employment(ONLY_PERSONAL_EMAIL_INDIVIDUAL),
                create_employment(INDIVIDUAL_WITH_ONLY_PERSONAL_PHONE),
                create_employment(TEST_INDIVIDUAL_WITHOUT_PHONES),
            ]
        }
    )


@urlmatch(netloc='api.tryfinch.com', path='/employer/employment')
def fake_employment_without_type(url, request):
    return json.dumps(
        {
            'responses': [
                create_employment_without_type(TEST_INDIVIDUAL),
                create_employment_without_type(TEST_MANAGER),
                create_employment_without_type(TEST_INDIVIDUAL_WITHOUT_EMAILS),
                create_employment_without_type(
                    TEST_INDIVIDUAL_WITHOUT_EMAILS_NEITHER_MANAGER
                ),
                create_employment_without_type(INTEGRATIONS_PAVE_USER),
                create_employment_without_type(USER_WITH_MANAGER_THAT_DONT_HAVE_EMAIL),
                create_employment_without_type(ONLY_PERSONAL_EMAIL_INDIVIDUAL),
                create_employment_without_type(INDIVIDUAL_WITH_ONLY_PERSONAL_PHONE),
                create_employment_without_type(TEST_INDIVIDUAL_WITHOUT_PHONES),
            ]
        }
    )


@urlmatch(netloc=r'api.tryfinch.com', path='/employer/company')
def call_fail_company(url, request):
    return mock_response(
        status_code=500,
        content='{"message": "Server Error", "name":"internal_server_error"} ',
    )


def create_company_response():
    return json.dumps(
        {'legal_name': TEST_COMPANY, 'locations': [TEST_LOCATION, TEST_LOCATION_2]}
    )


def create_access_token_response():
    return json.dumps({'access_token': 'token'})


def _get_testing_emails(individual, only_personal_email=False):
    first_name = individual["first_name"].lower()
    last_name = individual["last_name"].lower()

    def _get_personal_email() -> str:
        if first_name == 'integrations':
            return f'{first_name}@{last_name}.com'
        return f'{first_name}@example.com'

    def _get_work_email() -> str:
        if first_name == 'integrations':
            return f'{first_name}@{last_name}.com'
        return f'{first_name}@heylaika.com'

    emails = (
        [{'data': _get_personal_email(), 'type': 'personal'}]
        if only_personal_email
        else [
            {'data': _get_personal_email(), 'type': 'personal'},
            {'data': _get_work_email(), 'type': 'work'},
        ]
    )
    return emails


def _get_testing_phones(only_personal_phone=False):
    phones = (
        [{'data': PHONE_NUMBER, 'type': 'personal'}]
        if only_personal_phone
        else [
            {'data': PHONE_NUMBER, 'type': 'personal'},
            {'data': PHONE_NUMBER, 'type': 'work'},
        ]
    )
    return phones


def create_detail(
    individual,
    with_emails=True,
    with_phones=True,
    only_personal_email=False,
    only_personal_phone=False,
):
    emails = (
        None
        if not with_emails
        else _get_testing_emails(individual, only_personal_email)
    )

    phones = None if not with_phones else _get_testing_phones(only_personal_phone)

    return {
        'individual_id': individual['id'],
        'code': 200,
        'body': {
            **individual,
            'emails': emails,
            'phone_numbers': phones,
            'dob': "1993-04-08",
            'residence': TEST_LOCATION,
        },
    }


def create_employment(individual):
    return {
        'individual_id': individual['id'],
        'code': 200,
        'body': {
            **individual,
            'title': 'SE',
            'employment': {'type': 'employee', 'subtype': 'full_time'},
            'start_date': '2019-12-29',
            'end_date': None,
            'is_active': True,
            'location': TEST_LOCATION,
        },
    }


def create_employment_without_type(individual):
    return {
        'individual_id': individual['id'],
        'code': 200,
        'body': {
            **individual,
            'title': 'SE',
            'employment': {'subtype': 'full_time'},
            'start_date': '2019-12-29',
            'end_date': None,
            'is_active': True,
            'location': TEST_LOCATION,
        },
    }


def _load_response(file_name):
    parent_path = Path(__file__).parent
    with open(parent_path / file_name, 'r') as file:
        return file.read()


def fake_employments_response():
    return _load_response('employments_response.json')
