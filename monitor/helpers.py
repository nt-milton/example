from collections import Counter

from user.models import User


def get_monitors_status_stats(organization_monitors):
    status_list = [monitor.status.lower() for monitor in organization_monitors]
    return dict(Counter(status_list))


def validate_user_monitor_exclusion_event(user: User) -> str:
    return ' '.join(str(user).split()) if user else ''
