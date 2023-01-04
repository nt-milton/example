from unittest.mock import patch

import pytest

from certification.tests.factory import create_certification
from control.constants import MAX_OWNER_LIMIT_PER_CONTROL, UNASSIGNED_OWNER_ID
from control.helpers import (
    fill_max_owners,
    filter_by_certification_code_query,
    get_filter_query,
)
from control.models import Control
from control.mutations import validate_owners_quantity
from control.types import ControlType
from feature.constants import new_controls_feature_flag
from feature.models import Flag
from laika.tests.factory import mock_info_context_user
from organization.tests.factory import create_organization
from user.tests import create_user


@pytest.fixture
def organization():
    return create_organization(name='Laika Dev')


@pytest.fixture(scope="function")
def owner_list(request, transactional_db, organization):
    return [
        create_user(
            organization,
            email=owner_email,
        )
        for owner_email in request.param
    ]


@pytest.mark.parametrize(
    'owner_list',
    [
        (['john@superadmin.com', 'john@example2.com', 'john@example3.com']),
        (['john@superadmin.com', 'john@example2.com']),
        (['john@superadmin.com']),
        ([]),
    ],
    indirect=True,
)
def test_owners(owner_list, transactional_db, organization):
    m_c = Control()
    m_c.organization = organization

    owner_email_list = [owner_item.email for owner_item in owner_list]

    m_c.owners = owner_email_list

    assert m_c.owners == owner_list


@patch('control.types.map_permissions', return_value='permissions_data')
def test_resolve_permissions(mock_map_permissions):
    ct = ControlType()
    ct.owners = ['mock_owner1', 'mock_owner2']
    ct.approver = 'mock_approver'
    ct.administrator = 'mock_administrator'

    mi = mock_info_context_user('my_user_test')

    expected = ct.resolve_permissions(mi)

    expected_parameters = {
        'logged_user': 'my_user_test',
        'entity_name': 'control',
        'users': ['mock_owner1', 'mock_owner2', 'mock_approver', 'mock_administrator'],
    }

    mock_map_permissions.assert_called_with(
        expected_parameters['logged_user'],
        expected_parameters['entity_name'],
        expected_parameters['users'],
    )

    assert expected == 'permissions_data'


@pytest.mark.parametrize(
    'emails',
    [
        (['other@guy.com', 'tom@mate.com', 'example4@antenas.com']),
        (['example@appe.com', 'apple@window.com']),
        (['no@domain.com']),
        ([]),
        None,
    ],
)
def test_fill_max_owners(emails):
    result = fill_max_owners(emails)

    assert len(result) == MAX_OWNER_LIMIT_PER_CONTROL


def test_validate_owners_quantity():
    with pytest.raises(Exception):
        validate_owners_quantity(
            ['a@airplane.com', 'b@boy.com', 'c@charlie.com', 'd@delta.com']
        )


def test_get_filter_query_all_filters(transactional_db, organization):
    filters = {
        'status': ['IMPLEMENTED'],
        'health': ['NEEDS_ATTENTION', 'OPERATIONAL'],
        'pillar': [13],
        'tag': [2360, 1592],
        'search': '',
    }

    result = get_filter_query(filters, None, organization)
    expected = (
        "(AND: ('status_uppercase__in', ['IMPLEMENTED']), "
        "('pillar_id__in', [13]), ('tags__id__in', [2360, 1592]))"
    )

    assert str(result) == expected


def test_get_filter_query_no_certifications(transactional_db, organization):
    filters = {
        'status': ['IMPLEMENTED'],
        'health': ['NEEDS_ATTENTION', 'OPERATIONAL'],
        'framework': [],
        'pillar': [13],
        'tag': [2360, 1592],
        'search': '',
    }

    result = get_filter_query(filters, None, organization)
    expected = (
        "(AND: ('status_uppercase__in', ['IMPLEMENTED']), "
        "('pillar_id__in', [13]), ('tags__id__in', [2360, 1592]))"
    )

    assert str(result) == expected


def test_get_filter_unassigned_owners(transactional_db, organization):
    filters = {'owners': [UNASSIGNED_OWNER_ID]}

    result = get_filter_query(filters, None, organization)
    expected = "(AND: ('owner1__isnull', True))"

    assert str(result) == expected


def test_get_filter_owners(transactional_db, organization):
    filters = {'owners': [12, 454]}

    result = get_filter_query(filters, None, organization)
    expected = (
        "(AND: (OR: ('owner1__id__in', [12, 454]), "
        "('owner2__id__in', [12, 454]), ('owner3__id__in', [12, 454])))"
    )

    assert str(result) == expected


def test_get_filter_owners_and_unassigned(transactional_db, organization):
    filters = {'owners': [UNASSIGNED_OWNER_ID, 12, 454]}

    result = get_filter_query(filters, None, organization)
    expected = (
        "(AND: (OR: ('owner1__isnull', True), "
        "('owner1__id__in', [12, 454]), ('owner2__id__in', [12, 454]), "
        "('owner3__id__in', [12, 454])))"
    )

    assert str(result) == expected


def test_get_filter_query_search_by_reference_id(transactional_db, organization):
    filters = {'search': 'RA-12'}

    result = get_filter_query(filters, None, organization)
    expected = (
        "(AND: (OR: ('name__unaccent__icontains', 'RA-12'), "
        "('reference_id__unaccent__icontains', 'RA-12')))"
    )
    assert str(result) == expected


def test_get_filter_query_search_by_display_id(transactional_db, organization):
    filters = {'search': '12'}
    # Disable new_controls feature flag enabled by default to the organization
    new_controls_ff_instance = Flag.objects.get(
        name=new_controls_feature_flag, organization=organization
    )
    new_controls_ff_instance.is_enabled = False
    new_controls_ff_instance.save()

    result = get_filter_query(filters, None, organization)
    expected = (
        "(AND: (OR: ('name__unaccent__icontains', '12'), "
        "('display_id__icontains', '12')))"
    )
    assert str(result) == expected


def test_get_filter_query_search_by_display_id_with_prefix(
    transactional_db, organization
):
    filters = {'search': 'CTRL-12 '}
    # Disable new_controls feature flag enabled by default to the organization
    new_controls_ff_instance = Flag.objects.get(
        name=new_controls_feature_flag, organization=organization
    )
    new_controls_ff_instance.is_enabled = False
    new_controls_ff_instance.save()

    result = get_filter_query(filters, None, organization)
    expected = (
        "(AND: (OR: ('name__unaccent__icontains', 'CTRL-12 '), "
        "('display_id__icontains', '12')))"
    )
    assert str(result) == expected


def test_get_filter_query_search_by_empty_display_id(transactional_db, organization):
    filters = {'search': 'text without numbers'}
    # Disable new_controls feature flag enabled by default to the organization
    new_controls_ff_instance = Flag.objects.get(
        name=new_controls_feature_flag, organization=organization
    )
    new_controls_ff_instance.is_enabled = False
    new_controls_ff_instance.save()

    result = get_filter_query(filters, None, organization)
    expected = "(AND: ('name__unaccent__icontains', 'text without numbers'))"
    assert str(result) == expected


@pytest.mark.django_db
def test_filter_by_certification_code_query(organization):
    # To get just my compliance controls with the framework suffix
    new_controls_ff_instance = Flag.objects.get(
        name=new_controls_feature_flag, organization=organization
    )
    new_controls_ff_instance.is_enabled = True
    new_controls_ff_instance.save()

    soc_security_framework = create_certification(
        organization, ['CC1.1', 'CC1.2'], 'SOC 2 Security', True, code='SOC'
    )
    iso_27001_framework = create_certification(
        organization, ['CC1.1', 'CC1.2'], 'ISO 27001 (2013)', True, code='ISO'
    )
    certification_ids = [soc_security_framework.id, iso_27001_framework.id]

    result = filter_by_certification_code_query(certification_ids)
    expected = "(AND: ('reference_id__regex', '(SOC|ISO)$'))"

    assert str(result) == expected


@pytest.mark.django_db
def test_get_filter_query_frameworks(organization):
    # To get just my compliance controls with the framework suffix
    new_controls_ff_instance = Flag.objects.get(
        name=new_controls_feature_flag, organization=organization
    )
    new_controls_ff_instance.is_enabled = True
    new_controls_ff_instance.save()

    soc_security_framework = create_certification(
        organization, ['CC1.1', 'CC1.2'], 'SOC 2 Security', True, code='SOC'
    )
    iso_27001_framework = create_certification(
        organization, ['CC1.1', 'CC1.2'], 'ISO 27001 (2013)', True, code='ISO'
    )
    certification_ids = [soc_security_framework.id, iso_27001_framework.id]

    filters = {'framework': certification_ids}

    result = get_filter_query(filters, None, organization)
    expected = "(AND: ('reference_id__regex', '(SOC|ISO)$'))"

    assert str(result) == expected


@pytest.mark.django_db
def test_get_filter_query_frameworks_my_compliance_flag_disabled(organization):
    new_controls_ff_instance = Flag.objects.get(
        name=new_controls_feature_flag, organization=organization
    )
    new_controls_ff_instance.is_enabled = False
    new_controls_ff_instance.save()

    soc_security_framework = create_certification(
        organization, ['CC1.1', 'CC1.2'], 'SOC 2 Security', True, code='SOC'
    )
    iso_27001_framework = create_certification(
        organization, ['CC1.1', 'CC1.2'], 'ISO 27001 (2013)', True, code='ISO'
    )
    certification_ids = [soc_security_framework.id, iso_27001_framework.id]

    filters = {'framework': certification_ids}

    result = get_filter_query(filters, None, organization)
    expected = (
        "(AND: "
        "('certification_sections__certification_id__in', "
        f"[{soc_security_framework.id}, {iso_27001_framework.id}]))"
    )

    assert str(result) == expected
