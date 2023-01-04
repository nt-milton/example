from laika.schema import evidence_api_schema
from laika.settings import DEBUG


class DisableIntrospectionMiddleware:
    """
    This class hides the introspection.
    """

    def resolve(self, next, root, info, **kwargs):
        if info.field_name.lower() in ['__schema', '_introspection'] and not DEBUG:
            info.schema = evidence_api_schema
            return next(root, info, **kwargs)
        return next(root, info, **kwargs)
