from promise import Promise
from promise.dataloader import DataLoader

from user.models import User


class LoaderById(DataLoader):
    def __init__(self, model_type):
        super().__init__()
        self.model = model_type

    def batch_load_fn(self, keys):
        # if the model is User we use all_objects instead
        # of objects to get sof-deleted users as well
        values = (
            self.model.all_objects.in_bulk(keys)
            if self.model is User
            else self.model.objects.in_bulk(keys)
        )
        return Promise.resolve([values.get(key) for key in keys])


class ContextDataLoader(DataLoader):
    @classmethod
    def with_context(cls, context):
        loader = cls()
        setattr(loader, 'context', context)
        return loader
