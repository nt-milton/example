from pathlib import Path

from httmock import HTTMock, response, urlmatch

UNEXPECTED_API_OPERATION = 'Unexpected operation for Rippling fake api'


def fake_rippling_api():
    """This fake will intercept http calls to Rippling domain and
    It will use a fake implementation"""
    return HTTMock(fake_rippling_services, fake_auth)


def fake_rippling_api_without_permissions():
    """This fake will intercept http calls to Rippling domain and
    It will use a fake implementation"""
    return HTTMock(fake_rippling_services_without_permissions, fake_auth)


@urlmatch(netloc='sandbox.rippling.com', path='/api/o/token/')
def fake_auth(url, request):
    if 'refresh_token' in request.body or 'authorization_code' in request.body:
        return '{"access_token":"token", "refresh_token":"token"}'

    raise ValueError(UNEXPECTED_API_OPERATION)


def load_response(filename):
    with open(Path(__file__).parent / filename, 'r') as file:
        return file.read()


@urlmatch(netloc='sandbox.rippling.com', path='/api/platform/api')
def fake_rippling_services(url, request):
    if 'employees' in url.path:
        return load_response('raw_employee_response.json')
    elif 'companies' in url.path:
        return load_response('raw_companies_response.json')
    elif 'report_data' in url.path and request.method == 'POST':
        return load_response('raw_report_request_id_response.json')
    elif 'report_data' in url.path and request.method == 'GET':
        return load_response('raw_inventory_report_response.json')
    elif 'me' in url.path and request.method == 'GET':
        return load_response('raw_me_response.json')
    raise ValueError(UNEXPECTED_API_OPERATION)


@urlmatch(netloc='sandbox.rippling.com', path='/api/platform/api')
def fake_rippling_services_without_permissions(url, request):
    no_permission_response = response(
        content={'details': 'does not have permission to perform this operation.'},
        status_code=403,
    )
    if 'employees' in url.path:
        return load_response('raw_employee_response.json')
    elif 'companies' in url.path:
        return no_permission_response
    elif 'report_data' in url.path and request.method == 'POST':
        return no_permission_response
    elif 'report_data' in url.path and request.method == 'GET':
        return load_response('raw_inventory_report_response.json')
    raise ValueError(UNEXPECTED_API_OPERATION)
