from user.models import User


def get_email_domain_from_users(organization_id: str):
    active_users = User.objects.filter(is_active=True, organization_id=organization_id)
    first_user = list(active_users)[0]
    email_domain = first_user.email.split('@')[1]
    return f'@{email_domain}'
