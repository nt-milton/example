import logging

from laika.aws.ses import send_email, send_email_with_cc
from laika.settings import (
    DJANGO_SETTINGS,
    INVITE_NO_REPLY_EMAIL,
    LAIKA_CONCIERGE_REDIRECT,
    MAIN_ARCHIVE_MAIL,
    NO_REPLY_EMAIL,
    ORIGIN_LOCALHOST,
)
from organization.onboarding.onboarding_content import get_onboarding_contacts
from user.constants import USER_ROLES
from user.models import User
from user.utils.invite_user import invite_user

logger = logging.getLogger('user_invite_email_task')


def send_invite_concierge_email(user_email, context):
    login_link = LAIKA_CONCIERGE_REDIRECT or ORIGIN_LOCALHOST[1]

    template_context = {**context, 'login_link': login_link}

    logger.info(f'Sending concierge invite email to: {user_email}')
    send_email(
        subject='You’ve been invited to Laika Polaris!',
        from_email=INVITE_NO_REPLY_EMAIL,
        to=[user_email],
        template='email/invite_polaris_user.html',
        template_context=template_context,
    )

    return {'login_link': login_link, 'success': True}


def send_onboarding_technical_form(technical_poc: dict, organization, user):
    context = {
        'tech_user_first_name': technical_poc.get('first_name', ''),
        'user_first_name': user.first_name.capitalize(),
        'user_last_name': user.last_name.capitalize(),
        'organization_name': organization.name,
        'call_to_action_url': DJANGO_SETTINGS.get('ONBOARDING_TECH_TYPEFORM_FORM'),
    }

    cx_support_email = DJANGO_SETTINGS.get('CX_SUPPORT_EMAIL')
    technical_poc_email = technical_poc.get('email_address', None)
    if not technical_poc_email:
        logger.warning(
            f'No technical poc email found for organization {organization.id}'
        )
        return
    send_onboarding_technical_form_email(
        subject=f'{user.first_name} {user.last_name} assigned you a compliance task',
        to=technical_poc_email,
        template_context=context,
        cc=[cx_support_email, user.email],
    )


def send_onboarding_technical_form_email(subject, to, template_context, cc):
    logger.info(f'Sending email to: {to}')
    send_email_with_cc(
        subject=subject,
        from_email=NO_REPLY_EMAIL,
        to=[to],
        template='onboarding_technical_contact.html',
        template_context=template_context,
        cc=cc,
        bbc=[MAIN_ARCHIVE_MAIL],
    )


def send_invite_onboarding_contacts(contacts: list, organization, user):
    from user.mutations_schema.bulk_invite_users import (  # avoid circular import
        update_user,
    )

    try:
        invited_users = []
        for contact in contacts:
            if not contact:
                continue
            contact_to_invite = {
                'first_name': contact['first_name'],
                'last_name': contact['last_name'],
                'email': contact['email_address'],
                'role': USER_ROLES['ADMIN'],
                'organization_id': organization.id,
            }

            # we don't want to modify an existing user, so skip
            if contact_to_invite.get('email') == user.email:
                continue

            laika_user = User.objects.filter(
                email__iexact=contact_to_invite.get('email')
            ).first()
            if laika_user:
                if laika_user.organization.id != organization.id:
                    logger.warning(
                        'module: user.tasks.send_invite_onboarding_contacts Error:'
                        f' Service message: User {laika_user.email} already exists'
                        f' in another organization. organization {organization.id}.'
                    )
                    continue
                updated_user = update_user(laika_user, contact_to_invite)
                invited_users.append(updated_user)
            else:
                invited_user = invite_user(
                    organization, contact_to_invite, partial=False
                )
                invited_users.append(invited_user)
        return invited_users
    except Exception as e:
        logger.warning(
            'module: user.tasks.send_invite_onboarding_contacts Error:'
            f' Service message: {str(e)}. organization {organization.id}.'
        )
        return []


def process_invite_onboarding_users(questionary_response, organization, user):
    try:
        contacts = get_onboarding_contacts(questionary_response, user)

        logger.info(f'Inviting users to organization {organization.id}')
        invited_users = send_invite_onboarding_contacts(contacts, organization, user)

        logger.info(
            f'Invited users: {len(invited_users)} to organization {organization.id}'
        )

        technical_poc = next(
            (contact for contact in contacts if contact["role"] == "Technical"), None
        )
        technical_poc_email = technical_poc.get('email_address', None)
        can_send_technical_form = (
            technical_poc_email and technical_poc_email != user.email
        )
        if can_send_technical_form:
            logger.info('Sending technical form')
            send_onboarding_technical_form(technical_poc, organization, user)

    except Exception as e:
        logger.warning(
            'module: user.tasks.send_invite_onboarding_users'
            f' Error: {str(e)} Service message: Error sending user invitations from'
            f' onboarding form response. organization {organization.id}.'
        )
