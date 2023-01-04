from pathlib import Path

from httmock import HTTMock, urlmatch

PARENT_PATH = Path(__file__).parent


def fake_microsoft_intune_api():
    """This fake will intercept http calls to microsoft domain and
    It will use a fake implementation"""
    return HTTMock(_fake_microsoft_intune_api, _authentication)


@urlmatch(netloc='graph.microsoft.com')
def _fake_microsoft_intune_api(url, request):
    if 'deviceManagement' in url.path:
        return _managed_devices()

    raise ValueError('Unexpected operation for microsoft intune fake api')


def _managed_devices():
    path = PARENT_PATH / 'raw_managed_devices_response.json'
    return open(path, 'r').read()


@urlmatch(netloc='login.microsoftonline.com')
def _authentication(url, request):
    path = PARENT_PATH / 'raw_authentication_response.json'
    return open(path, 'r').read()
