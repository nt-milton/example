from urllib.parse import unquote

import pytest

from audit.utils.docusign import (
    get_docusign_query_string_from_fields,
    get_organization_address,
)
from organization.tests.factory import create_organization


@pytest.fixture
def organization():
    return create_organization(
        name='Laika Dev',
        address={
            'street1': '4259 Zappia Drive',
            'street2': 'James Drive',
            'city': 'Winchester',
            'state': 'Kentucky',
            'zip_code': '40391',
        },
    )


@pytest.mark.parametrize('prefix', [None, 3, [], {}])
def test_invalid_prefix(prefix):
    fields = {}

    with pytest.raises(ValueError, match='Invalid prefix'):
        get_docusign_query_string_from_fields(prefix, **fields)


@pytest.mark.parametrize(
    'prefix,fields,expect',
    [
        (
            'Client_',
            {'fullname': 'Bernice Wise', 'email': 'Bernice@xx.xx'},
            'Client_fullname=Bernice Wise&Client_email=Bernice@xx.xx',
        ),
        (
            'Prefix_',
            {
                'streetaddress': '10333 First St',
                'csz': 'Seattle WA 98122',
                'clientshortname': 'XXXX',
            },
            'Prefix_streetaddress=10333 First St&Prefix_csz=Seattle WA 98122'
            '&Prefix_clientshortname=XXXX',
        ),
    ],
)
def test_get_docusign_url(prefix, fields, expect):
    query_string = get_docusign_query_string_from_fields(prefix, **fields)
    assert unquote(query_string) == expect


@pytest.mark.functional
def test_get_organization_address(organization):
    street_address, zip_code = get_organization_address(organization)
    assert street_address == '4259 Zappia Drive James Drive'
    assert zip_code == 'Winchester Kentucky 40391'
