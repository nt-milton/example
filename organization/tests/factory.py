from address.models import Address
from dataroom.models import Dataroom
from feature.models import Flag
from organization.models import Organization
from user.constants import ONBOARDING


def create_organization(
    name='',
    flags=[],
    dataroom_name='Test Dataroom',
    address={},
    state=ONBOARDING,
    description='',
    website='',
    **kwargs
):
    """Build a test organization with the expected flags"""
    org = Organization.objects.create(
        name=name,
        state=state,
        description=description,
        website=website,
        **kwargs,
    )

    Dataroom.objects.create(organization=org, name=dataroom_name)
    if flags:
        feature_flags = [Flag(name=flag, is_enabled=True) for flag in flags]
        org.feature_flags.set(feature_flags, bulk=False)
    if bool(address):
        address_saved = Address.objects.create(**address)
        org.billing_address = address_saved
        org.save()
    return org
