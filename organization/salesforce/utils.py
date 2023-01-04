from datetime import datetime
from typing import Optional

import dateutil.parser

from organization.models import Organization
from organization.salesforce.constants import (
    ACCOUNT_STATUS_FIELD,
    COMPLIANCE_ARCHITECT_SALESFORCE_RELATION_FIELD,
    CONTRACT_SIGN_DATE_SALESFORCE_FIELD,
    CUSTOMER_SUCCESS_MANAGER_SALESFORCE_RELATION_FIELD,
    ID_SALESFORCE_FIELD,
    LAST_MODIFIED_BY,
    NAME_SALESFORCE_FIELD,
    WEBSITE_SALESFORCE_FIELD,
)
from organization.salesforce.salesforce_types import (
    OrganizationType,
    SalesforceAccountType,
)


def organization_adapter(data: dict) -> OrganizationType:
    return OrganizationType(
        sfdc_id=data.get(ID_SALESFORCE_FIELD),
        name=data.get(NAME_SALESFORCE_FIELD),
        website=data.get(WEBSITE_SALESFORCE_FIELD),
        customer_success_manager_user=get_user_email(
            data.get(CUSTOMER_SUCCESS_MANAGER_SALESFORCE_RELATION_FIELD)
        ),
        compliance_architect_user=get_user_email(
            data.get(COMPLIANCE_ARCHITECT_SALESFORCE_RELATION_FIELD)
        ),
        contract_sign_date=convert_sf_string_date_to_datetime(
            data.get(CONTRACT_SIGN_DATE_SALESFORCE_FIELD)
        ),
        account_status=data.get(ACCOUNT_STATUS_FIELD),
        last_modified_by=get_user_email(data.get(LAST_MODIFIED_BY)),
    )


def convert_sf_string_date_to_datetime(
    string_date: Optional[str],
) -> Optional[datetime]:
    if string_date:
        return dateutil.parser.parse(string_date)
    else:
        return None


def get_user_email(user) -> Optional[str]:
    if isinstance(user, dict):
        return user.get('Email')
    else:
        return user


def salesforce_account_adapter(organization: Organization) -> SalesforceAccountType:
    return SalesforceAccountType(
        name=organization.name,
        csm=organization.customer_success_manager_user.email,
        ca=organization.compliance_architect_user.email,
        website=organization.website,
    )


def create_body_message(organization: Organization) -> str:
    message = (
        f'*Name:* {organization.name}\n '
        f'*Website:* {organization.website}\n'
        '*Customer Success Manager:*'
        f' {organization.customer_success_manager_user.first_name} '
        f'{organization.customer_success_manager_user.last_name} \n'
        f'*Compliance Architect:* {organization.compliance_architect_user.first_name} '
        f'{organization.compliance_architect_user.last_name}'
    )
    return message
