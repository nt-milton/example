from sso.constants import OKTA
from sso.okta.request_bodies import generate_request_body

MAX_OKTA_PROVIDER_NAME = 100


def test_generate_request_body_long_org_name():
    large_org_name = (
        'Lorem ipsum dolor sit amet, consectetur '
        'adipiscing elit. Nam eget enim purus. Morbi'
        'vel magna eu velit tincidunt consectetur in id augue.'
    )
    request_body = generate_request_body(large_org_name, OKTA)
    assert len(request_body['name']) < MAX_OKTA_PROVIDER_NAME
