from search.types import CmdKVendorResultType


def search_vendor_qs(user, model):
    organization = user.organization

    results = model.objects.filter(organizationvendor__organization=organization)

    return results


def get_launchpad_dictionary(vendor):
    description = vendor.vendor.description
    if vendor.risk_rating:
        description += f' Vendor Criticality: {vendor.risk_rating}.'
    if vendor.operational_exposure:
        description += f' Operational Exposure: {vendor.operational_exposure}.'
    return CmdKVendorResultType(
        id=vendor.id,
        name=vendor.vendor.name,
        description=description,
        url=f"/vendors/{vendor.id}",
        text=vendor.additional_notes,
    )


def launchpad_mapper(model, organization_id):
    vendors = model.objects.filter(organization_id=organization_id)
    return list(map(get_launchpad_dictionary, vendors))
