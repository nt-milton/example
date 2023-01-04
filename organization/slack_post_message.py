import logging
from typing import Optional

from laika.settings import ENVIRONMENT
from laika.utils import slack

POLARIS_URLS = {
    'prod': 'https://polaris.heylaika.com',
    'rc': 'https://polaris-rc.heylaika.com',
    'staging': 'https://polaris-staging.heylaika.com',
    'dev': 'https://polaris-dev.heylaika.com',
    'local': 'https://polaris.heylaika.com',
}

PROD_CHANNEL = '#polaris-alerts'
LOWER_ENV_CHANNEL = '#polaris-alerts-test'
DEFAULT_MESSAGE = 'Unexpected error happened.'
PROD = 'prod'

logger = logging.getLogger(__name__)
SLACK_MAX_CHARACTERS = 3000


def post_error_message(message: Optional[str]):
    if message and len(message) > SLACK_MAX_CHARACTERS:
        logger.warning(f'post_error_message: {message}')
        message = (
            'Message is too long to be shown, please ask an administrator to check the '
            'logs and see what happened'
        )
    try:
        slack.post_block_error(
            channel=PROD_CHANNEL if ENVIRONMENT == PROD else LOWER_ENV_CHANNEL,
            subheader='Errors from salesforce sync',
            body=message if message else DEFAULT_MESSAGE,
        )
    except Exception as e:
        logger.warning(f'Error when posting slack message: {e}')


def post_info_message(
    organization_name: Optional[str],
    message_details: Optional[str],
    organization_id: Optional[str],
):
    try:
        slack.post_block_info_with_accessory(
            channel=PROD_CHANNEL if ENVIRONMENT == PROD else LOWER_ENV_CHANNEL,
            title='🎉 NEW ORGANIZATION ADDED 🎉',
            subheader=f'{organization_name} has been created in Polaris.',
            body=message_details if message_details else '',
            url_accessory=create_url_accessory(organization_id),
        )
    except Exception as e:
        logger.warning(f'Error when posting slack message: {e}')


def create_url_accessory(organization_id: Optional[str]) -> str:
    return (
        f'{POLARIS_URLS.get(ENVIRONMENT or PROD) or POLARIS_URLS[PROD]} '
        f'/organizations/{organization_id}/edit'
    )
