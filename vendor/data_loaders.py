from promise import Promise

from laika.data_loaders import ContextDataLoader, LoaderById
from vendor.models import Vendor, VendorCandidate


class VendorLoaders:
    def __init__(self, context):
        self.vendors_by_id = LoaderById(Vendor)
        self.vendor_candidates_by_vendor = VendorCandidateLoader().with_context(context)


class VendorCandidateLoader(ContextDataLoader):
    def batch_load_fn(self, keys: list):
        vendor_candidate = {
            vendor_candidate.vendor.id: vendor_candidate.number_of_users
            for vendor_candidate in VendorCandidate.objects.filter(
                vendor__in=keys, organization=self.context.user.organization
            )
        }
        return Promise.resolve(
            [vendor_candidate.get(candidate_id, []) for candidate_id in keys]
        )
