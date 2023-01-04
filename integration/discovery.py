from alert.constants import ALERT_TYPES
from program.utils.alerts import create_alert
from user.models import User
from vendor.models import (
    ALERTS_USER_ROLES,
    DISCOVERY_STATUS_CONFIRMED,
    DISCOVERY_STATUS_NEW,
    DISCOVERY_STATUS_PENDING,
    OrganizationVendor,
    Vendor,
    VendorCandidate,
    VendorDiscoveryAlert,
)


def create_vendor_discovery_alert(connection_account, new_vendors):
    number_of_new_vendors = [
        vendor for vendor in new_vendors if vendor.status == DISCOVERY_STATUS_NEW
    ]
    create_alerts_for_new_vendors_candidates(
        organization=connection_account.organization,
        number_of_new_vendors=len(number_of_new_vendors),
        integration=connection_account.integration.vendor.name,
    )


def create_alerts_for_new_vendors_candidates(
    organization, number_of_new_vendors, integration
):
    if number_of_new_vendors > 0:
        receivers = User.objects.filter(
            organization=organization, role__in=ALERTS_USER_ROLES
        )
        # importing here because it gives circular
        # dependency error ig imported from global
        from integration.slack.implementation import send_alert_to_slack
        from integration.slack.types import SlackAlert

        alert_type = ALERT_TYPES['VENDOR_DISCOVERY']
        slack_alert = SlackAlert(
            alert_type=alert_type,
            quantity=number_of_new_vendors,
            receiver=receivers.first(),
            integration=integration,
        )
        send_alert_to_slack(slack_alert)
        for receiver in receivers:
            create_alert(
                room_id=organization.id,
                receiver=receiver,
                alert_type=alert_type,
                alert_related_object={'quantity': number_of_new_vendors},
                alert_related_model=VendorDiscoveryAlert,
            )


def get_vendor_if_it_exists(vendor_name):
    vendor = Vendor.objects.filter(name=vendor_name).first()
    if vendor:
        return vendor
    vendor_candidate = (
        VendorCandidate.objects.filter(name=vendor_name, vendor__isnull=False)
        .select_related('vendor')
        .first()
    )
    if vendor_candidate:
        return vendor_candidate.vendor


def exclude_existing_vendor_candidates(organization, vendor_names):
    for vendor_name in vendor_names:
        vendor_candidate = VendorCandidate.objects.filter(
            name__iexact=vendor_name, organization=organization
        )
        organization_vendor = OrganizationVendor.objects.filter(
            vendor__name__iexact=vendor_name, organization=organization
        )
        if not (vendor_candidate.exists() or organization_vendor.exists()):
            yield vendor_name


def validate_scopes_for_vendor_candidates(connection_account, vendor_scopes):
    scopes = connection_account.authentication.get('scope', '')
    return vendor_scopes in scopes


def get_discovery_status_for_new_vendor_candidate(organization, vendor):
    relation_exists = OrganizationVendor.objects.filter(
        organization=organization, vendor=vendor
    ).exists()
    if relation_exists:
        return DISCOVERY_STATUS_CONFIRMED
    if vendor:
        return DISCOVERY_STATUS_NEW
    return DISCOVERY_STATUS_PENDING
