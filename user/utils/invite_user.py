import logging

from policy.utils.utils import create_policy_action_items
from user.utils.action_items import create_quickstart_action_items
from user.utils.invite_laika_user import invite_user_m
from user.utils.invite_partial_user import invite_partial_user_m

logger = logging.getLogger(__name__)


def invite_user(organization, parsed_user, partial):
    try:
        if partial:
            invitation_data = invite_partial_user_m(organization, parsed_user)
        else:
            invitation_data = invite_user_m(None, parsed_user, True)

        new_user = invitation_data['data']
        if new_user:
            if not partial:
                create_quickstart_action_items(new_user)
                create_policy_action_items(new_user)
            logger.info(f'User {parsed_user.get("email")} created')
        return new_user

    except Exception as e:
        message = 'Invite user has failed. Email was not provided'
        email = parsed_user['email']
        if email:
            message = f'Invite user with email: {email.strip()} has failed'
        logger.exception(f'{message}. Error {e}')
