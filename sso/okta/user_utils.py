import logging

from okta.exceptions import OktaAPIException

from laika.okta.api import OktaApi

logger = logging.getLogger('sso')
OktaApi = OktaApi()


def delete_okta_user(email: str):
    try:
        okta_user = OktaApi.get_user_by_email(email)

        if okta_user:
            logger.info(f'Deleting okta user {okta_user}')
            OktaApi.delete_user(okta_user.id)
    except OktaAPIException as err:
        logger.error(f'Error deleting inactive Okta user: {err}')
