import logging

from django.db import IntegrityError

from integration.discovery import get_vendor_if_it_exists
from integration.models import ConnectionAccount, OrganizationVendorUserSSO
from user.models import User
from vendor.models import OrganizationVendor

logger = logging.getLogger(__name__)


def show_vendor_user_log(
    user: dict,
    vendor_name: str,
    logger_name: str,
    connection_account: ConnectionAccount,
    user_exists: bool = False,
) -> None:
    primary_email = user.get('primaryEmail')
    log_message = f"Adding user: {primary_email} "
    if user_exists:
        log_message += f'to existing vendor: {vendor_name} '
    else:
        log_message += f'to new vendor: {vendor_name} '
    log_message += f' - Connection account {connection_account.id}'

    custom_logger = logging.getLogger(logger_name)
    custom_logger.info(log_message)


def create_sso_users(connection_account: ConnectionAccount, vendor_users: dict) -> None:
    if vendor_users:
        for vendor, sso_users in vendor_users.items():
            _vendor = get_vendor_if_it_exists(vendor)
            if not _vendor:
                continue
            org_vendor = OrganizationVendor.objects.filter(
                organization=connection_account.organization, vendor=_vendor
            ).first()
            create_organization_vendor_user(org_vendor, connection_account, sso_users)


def create_organization_vendor_user(
    org_vendor: OrganizationVendor,
    connection_account: ConnectionAccount,
    sso_users: list,
) -> None:
    if org_vendor:
        for sso_user in sso_users:
            user_email = sso_user.get('primaryEmail')
            user = User.objects.filter(email=user_email).first()
            logger.info(
                f'Creating Organization Vendor SSO User: {user_email} '
                f'for Organization: {connection_account.organization}'
            )
            try:
                sso_vendor_user = OrganizationVendorUserSSO(
                    connection_account=connection_account,
                    name=sso_user.get('name', '').get('fullName', ''),
                    email=user_email,
                    vendor=org_vendor,
                    user=user,
                )
                sso_vendor_user.save()
            except IntegrityError:
                logger.info(f'SSO User: {user_email} already exists')
                continue
