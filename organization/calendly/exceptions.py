class ResourceNotAvailable(Exception):
    """Intended to be used whenever some API does not return the required
    resource, so that we can retry the request"""

    pass
