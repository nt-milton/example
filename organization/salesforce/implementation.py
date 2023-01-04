import logging
from typing import Optional

from feature.constants import onboarding_v2_flag
from organization.constants import (
    COMPLETED_STATE,
    compliance_architect_user,
    customer_success_manager_user,
)
from organization.models import ACTIVE, ONBOARDING, TRIAL, Organization
from organization.salesforce.constants import (
    ACTIVE_TRIAL,
    CREATING,
    CUSTOMER,
    STATES,
    UPDATING,
)
from organization.salesforce.salesforce_exceptions import UserDoesNotExist
from organization.salesforce.salesforce_types import OrganizationType
from organization.salesforce.utils import create_body_message, organization_adapter
from organization.slack_post_message import post_info_message
from user.models import User

logger_name = __name__
logger = logging.getLogger(logger_name)
status_detail = []


def update_or_create_organization(
    payload: dict,
) -> tuple[Optional[Organization], list[str]]:
    status_detail.clear()
    try:
        logger.info(f'Syncing organization {payload} from Salesforce')
        sf_organization_data: OrganizationType = organization_adapter(payload)

        organization = Organization.objects.filter(
            sfdc_id=sf_organization_data.get('sfdc_id')
        ).first()

        if organization:
            validate_and_format_data_before_update(sf_organization_data)
            return (
                update_organization(sf_organization_data, organization.id),
                status_detail,
            )
        elif validate_data_before_create(sf_organization_data):
            return create_new_organization(sf_organization_data), status_detail
    except Exception as e:
        message = f'Error trying to get organization data: {e}'
        status_detail.append(message)
    return None, status_detail


def validate_and_format_data_before_update(sf_organization_data: OrganizationType):
    org_website = sf_organization_data.get('website')
    logger.info(
        f'Organization with name {sf_organization_data.get("name")} already exists in'
        ' Polaris.'
    )
    if org_website and Organization.objects.filter(website=org_website).exists():
        sf_organization_data.pop('website')
        logger.warning(f'Organization website {org_website} already exists.')


def validate_data_before_create(
    sf_organization_data: OrganizationType,
) -> bool:
    org_status = sf_organization_data.get('account_status')
    org_name = sf_organization_data.get('name')

    if not are_all_required_fields(sf_organization_data) or not is_a_valid_state(
        CREATING, org_status, org_name
    ):
        return False

    org_website = sf_organization_data.get('website')

    logger.info(f'Organization with name {org_name} does not exist in Polaris.')

    if Organization.objects.filter(website=org_website).exists():
        message = (
            f'Error when validating data before creating organization: *{org_name}* '
            f'Website: {org_website} already exists. Organization had not been created.'
        )
        status_detail.append(message)
        logger.warning(message)
        return False
    return True


def create_new_organization(
    organization: OrganizationType,
) -> Optional[Organization]:
    from organization.tasks import create_super_admin_users

    org_name = organization.get('name')

    csm_polaris = get_user(
        CREATING, org_name, organization.get('customer_success_manager_user')
    )
    ca_polaris = get_user(
        CREATING, org_name, organization.get('compliance_architect_user')
    )

    if not ca_polaris:
        raise UserDoesNotExist(
            'Compliance Architect does not exist in Laika. Org can not be created.'
        )
    if not csm_polaris:
        raise UserDoesNotExist(
            'Customer Success Manager does not exist in Laka. Org can not be created.'
        )

    state = STATES[organization.get('account_status') or CUSTOMER]
    logger.info(f'Creating new organization payload: {organization}')
    logger.info(f'organization: {organization.get("name")} selected status: {state}')

    org = Organization.objects.create(
        name=organization.get('name'),
        sfdc_id=organization.get('sfdc_id'),
        website=organization.get('website'),
        customer_success_manager_user=csm_polaris,
        compliance_architect_user=ca_polaris,
        contract_sign_date=organization.get('contract_sign_date'),
        state=state,
    )
    logger.info(f'Organization {org.name} has been created in Polaris.')

    if org:
        create_super_admin_users(org)
        post_info_message(
            org.name,
            create_body_message(org),
            org.id.hex,
        )

    return org


def are_all_required_fields(organization: OrganizationType) -> bool:
    for key, value in organization.items():
        if not value:
            error_message = (
                f'The field {key} is missing. '
                'This field is required in order to create an org in Polaris. '
                f'Organization: *{organization.get("name")}*'
            )
            status_detail.append(error_message)
            logger.warning(error_message)
            return False
    return True


def is_a_valid_state(
    action: str, status: Optional[str], organization_name: Optional[str]
) -> bool:
    if not status or status not in STATES:
        error_message = (
            f'{status} state from Salesforce is not valid in Laika on {action}. '
            f'Organization: *{organization_name}*'
        )
        status_detail.append(error_message)
        return False
    return True


def update_organization_details(org: Organization, organization_sf: OrganizationType):
    is_org_updated = False
    state_polaris = map_org_status(org, organization_sf.get('account_status'))
    fields_to_update = get_fields_to_update(organization_sf, state_polaris)

    for key, value in fields_to_update.items():
        if value:
            setattr(org, key, value)
            is_org_updated = True
            logger.info(
                f'sfdc sync field: {key}, value: {value}, organization: {org.name}'
            )

    if is_org_updated:
        org.save()
        logger.info(f'Organization {org.name} details have been updated.')
    else:
        logger.info(f'Organization {org.name} details were not updated by sfdc sync.')


def update_organization_csm(organization_laika_id, organization_sf):
    from organization.mutations import update_csm_user

    org = Organization.objects.get(id=organization_laika_id)

    csm_polaris = get_user(
        UPDATING,
        organization_sf.get('name'),
        organization_sf.get('customer_success_manager_user'),
    )

    if not csm_polaris or not csm_polaris.email:
        return

    if validate_user_updated(csm_polaris, org.customer_success_manager_user):
        logger.info(f'CSM user will be updated for organization {org.id}')
        update_csm_user(org, {customer_success_manager_user: csm_polaris})


def update_organization_ca(organization_laika_id, organization_sf):
    from organization.mutations import update_ca_user

    org = Organization.objects.get(id=organization_laika_id)

    ca_polaris = get_user(
        UPDATING,
        organization_sf.get('name'),
        organization_sf.get('compliance_architect_user'),
    )

    if not ca_polaris or not ca_polaris.email:
        return

    if validate_user_updated(ca_polaris, org.compliance_architect_user):
        logger.info(f'CA user will be updated for organization {org.id}')
        update_ca_user(org, {compliance_architect_user: ca_polaris})


def update_organization(
    organization_sf: OrganizationType, organization_laika_id: str
) -> Optional[Organization]:
    org = Organization.objects.get(id=organization_laika_id)
    update_organization_details(org, organization_sf)
    update_organization_csm(organization_laika_id, organization_sf)
    update_organization_ca(organization_laika_id, organization_sf)
    return org


def validate_user_updated(new_user: User, old_user: User) -> bool:
    if new_user.email != old_user.email:
        logger.info(f'Updating new_user: {new_user.email}, old_user: {old_user.email}')
        return True
    return False


def get_fields_to_update(
    organization_sf: OrganizationType,
    state: Optional[str],
) -> dict:
    return {
        'sfdc_id': organization_sf.get('sfdc_id'),
        'name': organization_sf.get('name'),
        'website': organization_sf.get('website'),
        'contract_sign_date': organization_sf.get('contract_sign_date'),
        'state': state,
    }


def is_on_boarding_completed(organization: Organization) -> bool:
    is_completed: bool = False
    org_on_boarding = organization.onboarding.first()

    if organization.is_flag_active(onboarding_v2_flag):
        if org_on_boarding.state_v2 == COMPLETED_STATE:
            is_completed = True
    elif org_on_boarding.state == COMPLETED_STATE:
        is_completed = True
    return is_completed


def map_org_status(organization: Organization, state: Optional[str]) -> Optional[str]:
    if organization.state in [ACTIVE, ONBOARDING]:
        return None
    if organization.state == TRIAL and state == CUSTOMER:
        if is_on_boarding_completed(organization):
            return ACTIVE
        return ONBOARDING
    if organization.state == TRIAL and state == ACTIVE_TRIAL:
        return None
    message = (
        f'salesforce state: {state} is not valid in laika for '
        f'organization: {organization}'
    )
    status_detail.append(message)
    logger.warning(message)
    return None


def get_user(
    action: str, organization_name: Optional[str], user_email: Optional[str]
) -> Optional[User]:
    if not user_email:
        return None
    try:
        logger.info(f'Getting user with email {user_email}')
        return User.objects.get(email=user_email)
    except User.DoesNotExist:
        error_message = (
            f'Error on {action} organization: *{organization_name}*. '
            'User from Salesforce with the email: '
            f'{user_email} does not exist in Laika.'
        )
        status_detail.append(error_message)
        return None
