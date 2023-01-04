from promise import Promise

from laika.data_loaders import ContextDataLoader, LoaderById
from user.models import User
from user.utils.associate_users_with_lo import get_user_lo_associations


class UserLoaders:
    def __init__(self):
        self.users_by_id = LoaderById(User)
        self.lo_user_ids = LOUserIdsLoader()


class LOUserIdsLoader(ContextDataLoader):
    """
    LO Users Ids loader
    """

    def batch_load_fn(self, keys: list) -> Promise:
        users_with_lo = get_user_lo_associations(keys[0].organization_id)
        return Promise.resolve([users_with_lo.get(user.id, {}) for user in keys])
