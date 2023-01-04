from laika.aws.cognito import create_user
from laika.utils.exceptions import ServiceException
from user.constants import CONCIERGE_ROLES
from user.tasks import send_invite_concierge_email


def create_cognito_concierge_user(user_data):
    email = user_data.get('email')

    if not user_data.get('permission') in CONCIERGE_ROLES.values():
        raise ServiceException(f'Invalid permission for user {email}')

    create_user_data = {
        'role': user_data.get('permission'),
        'email': email,
        'last_name': user_data.get('last_name'),
        'first_name': user_data.get('first_name'),
    }

    return create_user(create_user_data)


def send_concierge_user_email_invitation(user, cognito_user, sender='Admin'):
    email_context = {
        'name': sender,
        'title': 'You are invited to Laika Polaris',
        'hero_title': 'Welcome to Polaris!',
        'hero_subtitle': 'Experience the new way to manage organizations in Laika!',
        'username': user.email,
        'password': cognito_user.get('temporary_password'),
    }

    return send_invite_concierge_email(user.email, email_context)
