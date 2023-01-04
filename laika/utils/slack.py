import json
from datetime import datetime

import requests

from laika import settings


def post_message(channel, text='', attachments=[], blocks=[]):
    response = requests.post(
        'https://slack.com/api/chat.postMessage',
        headers={
            'Content-type': 'application/json',
            'Authorization': f'Bearer {settings.SLACK_TOKEN}',
        },
        data=json.dumps(
            {
                'icon_emoji': ':chart_with_upwards_trend:',
                'token': settings.SLACK_TOKEN,
                'channel': channel,
                'text': text,
                'blocks': json.dumps(blocks),
                'attachments': attachments,
                'as_user': True,
            }
        ),
    )
    response.raise_for_status()

    if not response.json().get('ok'):
        raise Exception(response.json())


# slack.post_block_error(
#     channel='#polaris-alerts-test',
#     subheader='Testing error messages',
#     body='The user you are trying to add does not exist in our database',
# )
def post_block_error(
    channel: str, title: str = '', subheader: str = '', body: str = ''
):
    message = [
        {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': '.\n.',
                'verbatim': False,
            },
        },
        {
            'type': 'header',
            'text': {
                'type': 'plain_text',
                'text': title or '‼️️ NEW ERROR FOUND ‼️',
            },
        },
        {
            'type': 'context',
            'elements': [
                {
                    'text': (
                        f'*{datetime.now().strftime("%Y/%m/%d")}* |  '
                        f'{subheader} | Laika Bot'
                    ),
                    'type': 'mrkdwn',
                }
            ],
        },
        {'type': 'divider'},
        {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': body or '',
            },
        },
        {'type': 'divider'},
        {
            'type': 'context',
            'elements': [
                {
                    'type': 'mrkdwn',
                    'text': (
                        'This is an auto-generated messages from Laika. Please '
                        'contact an administrator if you have questions.'
                    ),
                }
            ],
        },
        {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': '.\n.',
                'verbatim': False,
            },
        },
    ]

    post_message(blocks=message, channel=channel)


def post_block_info_with_accessory(
    channel: str,
    title: str = '',
    subheader: str = '',
    body: str = '',
    url_accessory: str = '',
):
    message = [
        {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': '.\n.',
                'verbatim': False,
            },
        },
        {
            'type': 'header',
            'text': {
                'type': 'plain_text',
                'text': title or '🎉 NEW MESSAGE 🎉',
            },
        },
        {
            'type': 'context',
            'elements': [
                {
                    'text': (
                        f'*{datetime.now().strftime("%Y/%m/%d")}* |  '
                        f'{subheader} Laika Bot'
                    ),
                    'type': 'mrkdwn',
                }
            ],
        },
        {'type': 'divider'},
        {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': body or '',
            },
            'accessory': {
                'type': 'button',
                'text': {
                    'type': 'plain_text',
                    'text': 'Go to details',
                    'emoji': True,
                },
                'value': 'click_me_123',
                'url': url_accessory,
                'action_id': 'button-action',
            },
        },
        {'type': 'divider'},
        {
            'type': 'context',
            'elements': [
                {
                    'type': 'mrkdwn',
                    'text': (
                        'This is an auto-generated messages from Laika. Please '
                        'contact an administrator if you have questions.'
                    ),
                }
            ],
        },
        {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': '.\n.',
                'verbatim': False,
            },
        },
    ]

    post_message(blocks=message, channel=channel)
