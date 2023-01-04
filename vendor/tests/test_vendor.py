import pytest as pytest

from certification.models import Certification
from vendor.tests.queries import (
    CREATE_ORGANIZATION_VENDOR_MUTATION,
    GET_ORGANIZATION_VENDOR,
    UPDATE_ORGANIZATION_VENDOR_MUTATION,
)


@pytest.fixture
def certification():
    return Certification.objects.create(name='SOC')


@pytest.mark.functional(permissions=['vendor.add_organizationvendor'])
def test_create_organization_vendor(graphql_client, certification):
    query_response = create_org_vendor(certification, graphql_client)
    assert query_response['data']['createOrganizationVendor']['success']


@pytest.mark.functional(permissions=['vendor.add_organizationvendor'])
def test_get_organization_vendor_with_categories_and_certs(
    graphql_client, certification
):
    create_org_vendor(certification, graphql_client)

    organization = graphql_client.context['organization']
    query_response = graphql_client.execute(
        GET_ORGANIZATION_VENDOR,
        variables={'id': organization.organization_vendors.first().id},
    )

    vendor_response = query_response['data']['organizationVendor']
    assert vendor_response['vendor']['categories'][0]['id']
    assert vendor_response['vendor']['certifications'][0]['id']


@pytest.mark.functional(permissions=['vendor.add_organizationvendor'])
def test_update_organization_vendor_with_no_categories_nor_certifications(
    graphql_client, certification
):
    create_org_vendor(certification, graphql_client)

    organization = graphql_client.context['organization']
    query_response = graphql_client.execute(
        UPDATE_ORGANIZATION_VENDOR_MUTATION,
        variables={
            'id': organization.organization_vendors.first().id,
            'input': dict(categoryNames=[], certificationIds=[]),
        },
    )
    assert query_response['data']['updateOrganizationVendor']['success']

    query_response = graphql_client.execute(
        GET_ORGANIZATION_VENDOR,
        variables={'id': organization.organization_vendors.first().id},
    )

    vendor_response = query_response['data']['organizationVendor']
    assert len(vendor_response['vendor']['categories']) == 0
    assert len(vendor_response['vendor']['certifications']) == 0


def create_org_vendor(certification, graphql_client):
    return graphql_client.execute(
        CREATE_ORGANIZATION_VENDOR_MUTATION,
        variables={
            'input': dict(
                name='test-vendor',
                fileName='',
                fileContents='',
                website='test.com',
                categoryNames=["category test"],
                description='test',
                certificationIds=[certification.id],
                riskAssessmentDate='2022-11-01',
            )
        },
    )
