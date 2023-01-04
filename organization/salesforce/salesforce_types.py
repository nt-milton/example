from datetime import datetime
from typing import Optional

from typing_extensions import TypedDict


class OrganizationType(TypedDict, total=False):
    sfdc_id: Optional[str]
    name: Optional[str]
    website: Optional[str]
    customer_success_manager_user: Optional[str]
    compliance_architect_user: Optional[str]
    contract_sign_date: Optional[datetime]
    account_status: Optional[str]
    last_modified_by: Optional[str]
    logo: Optional[str]


class SalesforceAccountType(TypedDict, total=False):
    sfdc_id: str
    name: str
    csm: Optional[str]
    ca: Optional[str]
    website: Optional[str]
    logo: Optional[str]
