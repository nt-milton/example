import tenacity

from integration.log_utils import increment_retry


def retry(*args, **kwargs):
    return tenacity.retry(*args, after=increment_retry, **kwargs)
