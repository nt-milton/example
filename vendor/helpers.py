from functools import reduce
from typing import Tuple

from django.db.models import Q

from organization.models import Organization
from user.models import User
from vendor.models import OrganizationVendor, OrganizationVendorStakeholder

FINANCIAL_EXPOSURE = {
    '1': Q(financial_exposure__lte=10000),
    '2': Q(financial_exposure__gt=10000, financial_exposure__lte=50000),
    '3': Q(financial_exposure__gt=50000, financial_exposure__lte=100000),
    '4': Q(financial_exposure__gt=100000),
}


def get_available_choice_from_tuple(tuple_choice: Tuple[Tuple[str, str]]):
    return [{'id': choice[0], 'name': choice[1]} for choice in tuple_choice]


def get_organization_vendor_filters(organization: Organization):
    stakeholders = OrganizationVendorStakeholder.objects.filter(
        organization_vendor__in=organization.organization_vendors.all()
    )
    users = User.objects.filter(
        organizationvendorstakeholder__in=stakeholders
    ).distinct()
    other_admin_ids = [
        {
            'name': u.get_full_name(),
            'id': u.id,
        }
        for u in users
    ]
    data = [
        {
            'category': 'Criticality Rating',
            'id': 'riskRating',
            'items': get_available_choice_from_tuple(
                OrganizationVendor.risk_rating.field.choices
            ),
        },
        {
            'category': 'Status',
            'id': 'status',
            'items': get_available_choice_from_tuple(
                OrganizationVendor.status.field.choices
            ),
        },
        {
            'category': 'Admin',
            'id': 'internalStakeholders',
            'items': [
                # Generate other admins ids
                *other_admin_ids
            ],
        },
        {
            'category': 'Financial Exposure',
            'id': 'financialExposure',
            'items': [
                {'name': '<$10,000', 'id': '1'},
                {'name': '$10,001 - $50,000', 'id': '2'},
                {'name': '$50,001 - $100,000', 'id': '3'},
                {'name': '>$100,000', 'id': '4'},
            ],
        },
        {
            'category': 'Operational Exposure',
            'id': 'operationalExposure',
            'items': get_available_choice_from_tuple(
                OrganizationVendor.operational_exposure.field.choices
            ),
        },
        {
            'category': 'Data Exposure',
            'id': 'dataExposure',
            'items': get_available_choice_from_tuple(
                OrganizationVendor.data_exposure.field.choices
            ),
        },
    ]
    return data


def get_vendor_filters(selected_filters: dict):
    simple_filters = ('risk_rating', 'status', 'operational_exposure', 'data_exposure')
    filters = Q()

    for field_name in simple_filters:
        value = selected_filters.get(field_name, [])
        if value:
            filters &= Q(**{f'{field_name}__in': value})

    internal_stakeholders = selected_filters.get('internal_stakeholders', [])
    financial_exposure = selected_filters.get('financial_exposure', [])

    if internal_stakeholders:
        filters &= Q(internal_stakeholders__in=internal_stakeholders)
        unassigned = '0' in internal_stakeholders
        if unassigned:
            filters |= Q(internal_stakeholders__isnull=True)

    financial_filters = [
        FINANCIAL_EXPOSURE[financial_option] for financial_option in financial_exposure
    ]
    if financial_filters:
        filters &= reduce(lambda a, b: a | b, financial_filters)

    return filters
