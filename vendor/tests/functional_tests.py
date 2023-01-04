from unittest.mock import patch

import pytest
from django.db.models import Q

from alert.models import Alert
from user.constants import ROLE_ADMIN
from user.models import User
from user.tests import create_user
from vendor.models import (
    ACTIVE_DISCOVERY_STATUSES,
    ALERTS_USER_ROLES,
    DISCOVERY_STATUS,
    DISCOVERY_STATUS_CONFIRMED,
    DISCOVERY_STATUS_IGNORED,
    DISCOVERY_STATUS_NEW,
    DISCOVERY_STATUS_PENDING,
    INACTIVE_DISCOVERY_STATUSES,
    OrganizationVendor,
    Vendor,
)

from .factory import (
    create_organization_vendor,
    create_service_accounts_for_testing,
    create_vendor,
    create_vendor_candidate,
)
from .queries import (
    CONFIRM_VENDOR_CANDIDATE_MUTATION,
    CREATE_ORGANIZATION_VENDOR_MUTATION,
    DELETE_ORGANIZATION_VENDOR_MUTATION,
    GET_FILTERED_VENDORS_WITH_ORDER_BY,
    GET_ORGANIZATION_VENDORS_FOR_ACCESS_REVIEW,
    UPDATE_ORGANIZATION_VENDOR_MUTATION,
    VENDOR_CANDIDATES_QUERY,
    VENDOR_FILTERS,
)


@pytest.mark.functional(permissions=['vendor.view_vendorcandidate'])
def test_vendor_candidate_query_without_vendors(graphql_client):
    organization = graphql_client.context['organization']
    for status in DISCOVERY_STATUS:
        create_vendor_candidate(
            organization, name=f'no vendor, {status[0]}', status=status[0]
        )
    query_response = graphql_client.execute(VENDOR_CANDIDATES_QUERY)
    vendor_candidates = query_response['data']['vendorCandidates']
    assert len(vendor_candidates['new']) == 0
    assert len(vendor_candidates['ignored']) == 0


@pytest.mark.functional(permissions=['vendor.view_vendorcandidate'])
def test_vendor_candidate_query_without_active_statuses(graphql_client):
    organization = graphql_client.context['organization']
    for status in INACTIVE_DISCOVERY_STATUSES:
        create_vendor_candidate(
            organization,
            name=f'vendor, {status}',
            status=status,
        )
    query_response = graphql_client.execute(VENDOR_CANDIDATES_QUERY)
    vendor_candidates = query_response['data']['vendorCandidates']
    assert len(vendor_candidates['new']) == 0
    assert len(vendor_candidates['ignored']) == 0


@pytest.mark.functional(permissions=['vendor.view_vendorcandidate'])
def test_vendor_candidate_query_with_active_vendors(graphql_client):
    organization = graphql_client.context['organization']
    for status in ACTIVE_DISCOVERY_STATUSES:
        create_vendor_candidate(
            organization,
            name=f'vendor, {status}',
            status=status,
            vendor=create_vendor(name=f'vendor, {status}'),
        )
    query_response = graphql_client.execute(VENDOR_CANDIDATES_QUERY)
    vendor_candidates = query_response['data']['vendorCandidates']
    assert len(vendor_candidates['new']) == 1
    assert len(vendor_candidates['ignored']) == 1


@pytest.fixture
def confirmed_vendor_candidate(graphql_organization):
    confirmed_vendor_name = 'confirmed'
    yield create_vendor_candidate(
        graphql_organization,
        name=confirmed_vendor_name,
        status=DISCOVERY_STATUS_CONFIRMED,
        vendor=create_vendor(name=confirmed_vendor_name),
    )


@pytest.fixture
def ignored_vendor_candidate(graphql_organization):
    ignored_vendor_name = 'ignored'
    yield create_vendor_candidate(
        graphql_organization,
        name=ignored_vendor_name,
        status=DISCOVERY_STATUS_IGNORED,
        vendor=create_vendor(name=ignored_vendor_name),
    )


@pytest.fixture
def new_vendor_candidate(graphql_organization):
    new_vendor_name = 'new'
    yield create_vendor_candidate(
        graphql_organization,
        name=new_vendor_name,
        status=DISCOVERY_STATUS_NEW,
        vendor=create_vendor(name=new_vendor_name),
    )


@pytest.fixture
def pending_vendor_candidate(graphql_organization):
    yield create_vendor_candidate(
        graphql_organization,
        name='pending',
    )


@pytest.fixture
def new_to_confirmed_vendor_candidate(graphql_organization):
    new_to_confirmed_vendor_name = 'confirmed'
    yield create_vendor_candidate(
        graphql_organization,
        name=new_to_confirmed_vendor_name,
        status=DISCOVERY_STATUS_NEW,
        vendor=create_vendor(name=new_to_confirmed_vendor_name),
    )


@pytest.fixture
def new_to_ignored_vendor_candidate(graphql_organization):
    new_to_ignored_vendor_name = 'ignored'
    yield create_vendor_candidate(
        graphql_organization,
        name=new_to_ignored_vendor_name,
        status=DISCOVERY_STATUS_NEW,
        vendor=create_vendor(name=new_to_ignored_vendor_name),
    )


@pytest.mark.functional(permissions=['vendor.add_organizationvendor'])
def test_confirm_vendor_candidates_mutation(
    graphql_client,
    new_to_confirmed_vendor_candidate,
    new_to_ignored_vendor_candidate,
    new_vendor_candidate,
    pending_vendor_candidate,
):
    organization = graphql_client.context['organization']
    receivers = User.objects.filter(
        organization=organization, role__in=ALERTS_USER_ROLES
    )
    receivers_ids = [receiver.id for receiver in receivers]
    query_response = graphql_client.execute(
        CONFIRM_VENDOR_CANDIDATE_MUTATION,
        variables={
            'confirmedVendorIds': [new_to_confirmed_vendor_candidate.vendor.id],
            'ignoredVendorIds': [new_to_ignored_vendor_candidate.vendor.id],
        },
    )
    vendor_ids = query_response['data']['confirmVendorCandidates']['vendorIds']
    new_to_confirmed_vendor_candidate.refresh_from_db()
    new_to_ignored_vendor_candidate.refresh_from_db()
    new_vendor_candidate.refresh_from_db()
    pending_vendor_candidate.refresh_from_db()
    assert len(vendor_ids) == 1
    assert new_to_confirmed_vendor_candidate.status == DISCOVERY_STATUS_CONFIRMED
    assert new_to_ignored_vendor_candidate.status == DISCOVERY_STATUS_IGNORED
    assert new_vendor_candidate.status == DISCOVERY_STATUS_NEW
    assert pending_vendor_candidate.status == DISCOVERY_STATUS_PENDING
    assert OrganizationVendor.objects.filter(
        organization=organization, vendor=new_to_confirmed_vendor_candidate.vendor
    ).exists()
    assert not Alert.objects.filter(receiver_id__in=receivers_ids).exists()


@pytest.mark.functional(permissions=['vendor.add_organizationvendor'])
def test_confirm_already_confirmed_vendor(graphql_client, confirmed_vendor_candidate):
    organization = graphql_client.context['organization']
    query_response = graphql_client.execute(
        CONFIRM_VENDOR_CANDIDATE_MUTATION,
        variables={
            'confirmedVendorIds': [confirmed_vendor_candidate.vendor.id],
            'ignoredVendorIds': [],
        },
    )
    vendor_ids = query_response['data']['confirmVendorCandidates']['vendorIds']
    confirmed_vendor_candidate.refresh_from_db()
    assert len(vendor_ids) == 0
    assert confirmed_vendor_candidate.status == DISCOVERY_STATUS_CONFIRMED
    assert not OrganizationVendor.objects.filter(
        organization=organization, vendor=confirmed_vendor_candidate.vendor
    ).exists()


@pytest.mark.functional(permissions=['vendor.add_organizationvendor'])
def test_do_not_mark_as_ignored_an_already_confirmed_vendor(
    graphql_client, confirmed_vendor_candidate
):
    organization = graphql_client.context['organization']
    query_response = graphql_client.execute(
        CONFIRM_VENDOR_CANDIDATE_MUTATION,
        variables={
            'confirmedVendorIds': [],
            'ignoredVendorIds': [confirmed_vendor_candidate.vendor.id],
        },
    )
    vendor_ids = query_response['data']['confirmVendorCandidates']['vendorIds']
    confirmed_vendor_candidate.refresh_from_db()
    assert len(vendor_ids) == 0
    assert confirmed_vendor_candidate.status == DISCOVERY_STATUS_CONFIRMED
    assert not OrganizationVendor.objects.filter(
        organization=organization, vendor=confirmed_vendor_candidate.vendor
    ).exists()


@pytest.mark.functional(permissions=['vendor.add_organizationvendor'])
def test_validate_status_when_confirming_and_ignoring_active_vendor(
    graphql_client, new_to_confirmed_vendor_candidate
):
    organization = graphql_client.context['organization']
    vendor_ids = [new_to_confirmed_vendor_candidate.vendor.id]
    query_response = graphql_client.execute(
        CONFIRM_VENDOR_CANDIDATE_MUTATION,
        variables={'confirmedVendorIds': vendor_ids, 'ignoredVendorIds': vendor_ids},
    )
    vendor_ids = query_response['data']['confirmVendorCandidates']['vendorIds']
    new_to_confirmed_vendor_candidate.refresh_from_db()
    assert len(vendor_ids) == 1
    assert new_to_confirmed_vendor_candidate.status == DISCOVERY_STATUS_CONFIRMED
    assert OrganizationVendor.objects.filter(
        organization=organization, vendor=new_to_confirmed_vendor_candidate.vendor
    ).exists()


@pytest.mark.functional
def test_signal_to_match_vendors_with_vendor_candidates_by_exact_name():
    vendor_name = 'vendor_name'
    vendor_candidate = create_vendor_candidate(name=vendor_name)
    vendor = create_vendor(name=vendor_name)
    vendor_candidate.refresh_from_db()
    assert vendor_candidate.vendor == vendor
    assert vendor_candidate.status == DISCOVERY_STATUS_NEW


@pytest.mark.functional
def test_signal_to_match_vendors_with_vendor_candidates_by_vendor_candidate():
    vendor_alias = 'vendor_alias'
    vendor_candidate = create_vendor_candidate(name=vendor_alias)
    vendor = create_vendor(name='vendor_name')
    vendor_candidate_with_vendor = create_vendor_candidate(
        name=vendor_alias, vendor=vendor
    )
    vendor_candidate.refresh_from_db()
    vendor_candidate_with_vendor.refresh_from_db()
    assert vendor_candidate.vendor == vendor
    assert vendor_candidate.status == DISCOVERY_STATUS_NEW
    assert vendor_candidate_with_vendor.status == DISCOVERY_STATUS_NEW


@pytest.mark.functional
def test_signal_to_update_the_list_if_an_organizationvendor_is_created():
    vendor = create_vendor()
    vendor_candidate = create_vendor_candidate(vendor=vendor)
    OrganizationVendor.objects.create(
        vendor=vendor, organization=vendor_candidate.organization
    )
    vendor_candidate.refresh_from_db()
    assert vendor_candidate.status == DISCOVERY_STATUS_CONFIRMED


@pytest.mark.functional
def test_signal_to_update_the_list_if_an_organizationvendor_is_removed():
    vendor = create_vendor()
    vendor_candidate = create_vendor_candidate(
        vendor=vendor, status=DISCOVERY_STATUS_CONFIRMED
    )
    organization_vendor = OrganizationVendor.objects.create(
        vendor=vendor, organization=vendor_candidate.organization
    )
    organization_vendor.delete()
    vendor_candidate.refresh_from_db()
    assert vendor_candidate.status == DISCOVERY_STATUS_IGNORED


@pytest.mark.functional(permissions=['vendor.add_organizationvendor'])
def test_create_duplicated_vendor(
    graphql_client,
):
    organization = graphql_client.context['organization']
    new_vendor_name = 'test-vendor'
    graphql_client.execute(
        CREATE_ORGANIZATION_VENDOR_MUTATION,
        variables={
            'input': dict(
                name=new_vendor_name,
                fileName='',
                fileContents='',
                website='test.com',
                categoryNames=[],
                description='test',
                certificationIds=[],
                riskAssessmentDate='2022-11-01',
            )
        },
    )

    assert OrganizationVendor.objects.filter(
        vendor__name=new_vendor_name, organization=organization
    ).exists()

    new_query_response = graphql_client.execute(
        CREATE_ORGANIZATION_VENDOR_MUTATION,
        variables={
            'input': dict(
                name=new_vendor_name,
                fileName='',
                fileContents='',
                website='test.com',
                categoryNames=[],
                description='test',
                certificationIds=[],
                riskAssessmentDate='2022-11-01',
            )
        },
    )
    error_message = f'{new_vendor_name} vendor already exists'
    query_message = new_query_response['errors'][0]['message']
    assert query_message == error_message


@pytest.mark.functional(permissions=['vendor.add_organizationvendor'])
def test_create_vendor_with_wrong_risk_assessment_date_value(
    graphql_client,
):
    new_vendor_name = 'test-vendor'
    wrong_format_date = '202a-11-01'
    query_response = graphql_client.execute(
        CREATE_ORGANIZATION_VENDOR_MUTATION,
        variables={
            'input': dict(
                name=new_vendor_name,
                fileName='',
                fileContents='',
                website='test.com',
                categoryNames=[],
                description='test',
                certificationIds=[],
                riskAssessmentDate=wrong_format_date,
            )
        },
    )

    error_message = (
        f'field "riskAssessmentDate": Expected type "Date", found "{wrong_format_date}"'
    )
    query_message = query_response['errors'][0]['message']
    assert error_message in query_message


@pytest.mark.functional()
def test_delete_organization_vendor(graphql_client, graphql_organization):
    vendor = create_vendor(is_public=False)
    organization_vendor = create_organization_vendor(graphql_organization, vendor)
    response = graphql_client.execute(
        DELETE_ORGANIZATION_VENDOR_MUTATION,
        variables={'input': {'vendorIds': [vendor.id]}},
    )
    delete_organization_vendor = response['data']['deleteOrganizationVendor']
    assert delete_organization_vendor['success']
    assert Vendor.objects.filter(id=vendor.id).exists()
    assert not OrganizationVendor.objects.filter(id=organization_vendor.id).exists()


@pytest.mark.functional(permissions=['vendor.add_organizationvendor'])
def test_update_organization_vendor(graphql_client, graphql_organization):
    vendor = create_vendor(is_public=False)
    organization_vendor = create_organization_vendor(graphql_organization, vendor)
    new_vendor_name = 'no logo vendor'
    response = graphql_client.execute(
        UPDATE_ORGANIZATION_VENDOR_MUTATION,
        variables={
            'input': dict(
                name=new_vendor_name,
                fileName='happy-monkey.png',
                fileContents='SG9sXDCzcSB0ZXh0',
                website='test.com',
                categoryNames=[],
                description='test',
                certificationIds=[],
                riskAssessmentDate='2022-11-01',
            ),
            'id': int(organization_vendor.id),
        },
    )
    update_organization_vendor = response['data']['updateOrganizationVendor']
    assert update_organization_vendor['success']


@pytest.mark.functional(permissions=['vendor.add_organizationvendor'])
def test_update_organization_vendor_without_logo(graphql_client, graphql_organization):
    vendor = create_vendor(is_public=False)
    organization_vendor = create_organization_vendor(graphql_organization, vendor)
    new_vendor_name = 'no logo vendor'
    response = graphql_client.execute(
        UPDATE_ORGANIZATION_VENDOR_MUTATION,
        variables={
            'input': dict(
                name=new_vendor_name,
                fileName=None,
                fileContents='',
                website='test.com',
                categoryNames=[],
                description='test',
                certificationIds=[],
                riskAssessmentDate='2022-11-01',
            ),
            'id': int(organization_vendor.id),
        },
    )
    update_organization_vendor = response['data']['updateOrganizationVendor']
    assert update_organization_vendor['success']


@pytest.mark.functional()
@pytest.mark.skip
def test_retrieve_vendor_filters(graphql_client):
    response = graphql_client.execute(VENDOR_FILTERS)

    def get_category(field_id: str):
        return lambda filter: filter['id'] == field_id

    low_med_high_items = [
        {'id': 'low', 'name': 'Low'},
        {'id': 'medium', 'name': 'Medium'},
        {'id': 'high', 'name': 'High'},
    ]
    data_exposure_items = [
        {'id': 'no_sensitive_data', 'name': 'No sensitive data'},
        {'id': 'customer_pii', 'name': 'Customer PII'},
        {'id': 'employee_pii', 'name': 'Employee PII'},
        {'id': 'customer_and_employee_pii', 'name': 'Customer & Employee PII'},
        {'id': 'company_financial_data', 'name': 'Company Financial Data'},
    ]
    status_items = [
        {'id': 'new', 'name': 'New'},
        {'id': 'requested', 'name': 'Requested'},
        {'id': 'review', 'name': 'In Review'},
        {'id': 'approved', 'name': 'Approved'},
        {'id': 'active', 'name': 'Active'},
        {'id': 'deprecated', 'name': 'Deprecated'},
        {'id': 'disqualified', 'name': 'Disqualified'},
    ]
    filters = response.get('data', {})
    filters = filters.get('filteredOrganizationVendors', {})
    filters = filters.get('filters', {})
    risk_rating = next(filter(get_category('riskRating'), filters), None)
    data_exposure = next(filter(get_category('dataExposure'), filters), None)
    operational_exposure = next(
        filter(get_category('operationalExposure'), filters), None
    )
    financial_exposure = next(filter(get_category('financialExposure'), filters), None)
    status = next(filter(get_category('status'), filters), None)
    internal_stakeholders = next(
        filter(get_category('internalStakeholders'), filters), None
    )

    assert response.get('errors') is None
    assert risk_rating['items'] == low_med_high_items
    assert data_exposure['items'] == data_exposure_items
    assert operational_exposure['items'] == low_med_high_items
    assert financial_exposure is not None
    assert status['items'] == status_items
    assert internal_stakeholders is not None


@pytest.mark.functional(permissions=['vendor.add_organizationvendor'])
def test_update_organization_vendor_stakeholder_no_UUID(
    graphql_client, graphql_organization
):
    vendor = create_vendor(is_public=False)
    organization_vendor = create_organization_vendor(graphql_organization, vendor)
    stakeholder = create_user(
        graphql_organization,
        email='john@admin.com',
        role=ROLE_ADMIN,
        first_name='john',
        last_name='doe',
        username='123',
    )
    response = graphql_client.execute(
        UPDATE_ORGANIZATION_VENDOR_MUTATION,
        variables={
            'input': dict(
                internalStakeholderIds=[
                    dict(sortIndex=0, stakeholderId=stakeholder.username)
                ]
            ),
            'id': int(organization_vendor.id),
        },
    )
    update_organization_vendor = response['data']['updateOrganizationVendor']
    assert update_organization_vendor['success']


@pytest.mark.functional(permissions=['vendor.add_organizationvendor'])
def test_update_organization_vendor_stakeholder_UUID(
    graphql_client, graphql_organization
):
    vendor = create_vendor(is_public=False)
    organization_vendor = create_organization_vendor(graphql_organization, vendor)
    stakeholder = create_user(
        graphql_organization,
        email='john@admin.com',
        role=ROLE_ADMIN,
        first_name='john',
        last_name='doe',
        username='0e54859d-50a6-4177-9f38-610f40a4c26b',
    )
    response = graphql_client.execute(
        UPDATE_ORGANIZATION_VENDOR_MUTATION,
        variables={
            'input': dict(
                internalStakeholderIds=[
                    dict(sortIndex=0, stakeholderId=stakeholder.username)
                ]
            ),
            'id': int(organization_vendor.id),
        },
    )
    update_organization_vendor = response['data']['updateOrganizationVendor']
    assert update_organization_vendor['success']


@pytest.mark.functional(permissions=['vendor.view_organizationvendor'])
def test_get_organization_vendors_for_access_review(
    graphql_client,
    graphql_organization,
):
    graphql_user = graphql_client.context.get('user')
    vendor = create_vendor('vendor')
    create_service_accounts_for_testing(graphql_organization, graphql_user, vendor)

    response = graphql_client.execute(
        GET_ORGANIZATION_VENDORS_FOR_ACCESS_REVIEW,
        variables={
            'id': vendor.id,
            'orderBy': [{'field': 'account_name', 'order': 'descend'}],
            'pagination': {
                'page': 1,
                'pageSize': 3,
            },
        },
    )

    service_accounts = response['data']['serviceAccountsPerVendor']['results']
    assert service_accounts == [
        {
            'id': '5',
            'username': 'lo_service_account_2',
            'connection': 'Connection Account',
            'email': 'user@heylaika.com',
            'groups': 'testing',
        },
        {
            'id': '4',
            'username': 'lo_service_account',
            'connection': 'Connection Account',
            'email': 'user@heylaika.com',
            'groups': 'testing',
        },
        {
            'id': '2',
            'username': 'lo user 2',
            'connection': 'Connection Account',
            'email': 'user@heylaika.com',
            'groups': 'testing testing',
        },
    ]


@pytest.mark.functional(permissions=['vendor.view_organizationvendor'])
def test_get_organization_vendors_for_access_review_not_show_deleted_accounts(
    graphql_client,
    graphql_organization,
):
    graphql_user = graphql_client.context.get('user')
    vendor = create_vendor('vendor')
    create_service_accounts_for_testing(graphql_organization, graphql_user, vendor)

    response = graphql_client.execute(
        GET_ORGANIZATION_VENDORS_FOR_ACCESS_REVIEW,
        variables={
            'id': vendor.id,
            'orderBy': [{'field': 'account_name', 'order': 'descend'}],
        },
    )

    service_accounts = response['data']['serviceAccountsPerVendor']['results']
    assert len(service_accounts) == 4


@pytest.mark.functional(permissions=['vendor.view_organizationvendor'])
@patch('vendor.schema.Q')
def test_retrieve_vendors_ordered_by_criticality_descend(
    mocked_q, graphql_client, graphql_organization
):
    # Mocking Q instance because UNACCENT function is not supported in sqlite
    mocked_q.return_value = Q()

    create_organization_vendors_for_testing(graphql_organization)

    response = graphql_client.execute(
        GET_FILTERED_VENDORS_WITH_ORDER_BY,
        variables={"orderBy": {"field": "risk_rating", "order": "descend"}},
    )

    data = response['data']['filteredOrganizationVendors']['data']
    ratings_from_response = [_vendor['riskRating'] for _vendor in data]

    expected_ordered_ratings = ['Critical', 'High', 'Medium', 'Low', '']

    assert response.get('errors') is None
    assert len(data) == 5
    assert expected_ordered_ratings == ratings_from_response


@pytest.mark.functional(permissions=['vendor.view_organizationvendor'])
@patch('vendor.schema.Q')
def test_retrieve_vendors_ordered_by_criticality_weight(
    mocked_q, graphql_client, graphql_organization
):
    # Mocking Q instance because UNACCENT function is not supported in sqlite
    mocked_q.return_value = Q()

    create_organization_vendors_for_testing(graphql_organization)

    response = graphql_client.execute(
        GET_FILTERED_VENDORS_WITH_ORDER_BY,
        variables={"orderBy": {"field": "risk_rating", "order": "descend"}},
    )

    data = response['data']['filteredOrganizationVendors']['data']
    rank_from_response = [_vendor['riskRatingRank'] for _vendor in data]

    expected_weight = {"critical": 4, "high": 3, "medium": 2, "low": 1, "": 0}

    assert response.get('errors') is None
    assert len(data) == 5
    assert expected_weight['critical'] == rank_from_response[0]
    assert expected_weight['high'] == rank_from_response[1]
    assert expected_weight['medium'] == rank_from_response[2]
    assert expected_weight['low'] == rank_from_response[3]
    assert expected_weight[''] == rank_from_response[4]


@pytest.mark.functional(permissions=['vendor.view_organizationvendor'])
@patch('vendor.schema.Q')
def test_retrieve_vendors_ordered_by_criticality_ascend(
    mocked_q, graphql_client, graphql_organization
):
    # Mocking Q instance because UNACCENT function is not supported in sqlite
    mocked_q.return_value = Q()

    create_organization_vendors_for_testing(graphql_organization)

    response = graphql_client.execute(
        GET_FILTERED_VENDORS_WITH_ORDER_BY,
        variables={"orderBy": {"field": "risk_rating", "order": "ascend"}},
    )

    data = response['data']['filteredOrganizationVendors']['data']
    ratings_from_response = [_vendor['riskRating'] for _vendor in data]

    expected_ordered_ratings = ['', 'Low', 'Medium', 'High', 'Critical']

    assert response.get('errors') is None
    assert len(data) == 5
    assert expected_ordered_ratings == ratings_from_response


def create_organization_vendors_for_testing(graphql_organization):
    vendor = create_vendor()
    create_organization_vendor(graphql_organization, vendor)
    create_organization_vendor(graphql_organization, vendor, 'low')
    create_organization_vendor(graphql_organization, vendor, 'medium')
    create_organization_vendor(graphql_organization, vendor, 'high')
    create_organization_vendor(graphql_organization, vendor, 'critical')
