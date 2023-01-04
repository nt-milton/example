import json
import logging
import os

import boto3

from laika.aws.secrets import REGION_NAME

logger = logging.getLogger('sns')

LEGACY_AWS_ACCESS_KEY = os.getenv('LEGACY_AWS_ACCESS_KEY')
LEGACY_AWS_SECRET_ACCESS_KEY = os.getenv('LEGACY_AWS_SECRET_ACCESS_KEY')
ENV = os.getenv('ENVIRONMENT') if os.getenv('ENVIRONMENT') != 'local' else 'development'


session = boto3.session.Session()
sns = session.client(
    'sns',
    region_name=REGION_NAME,
    aws_access_key_id=LEGACY_AWS_ACCESS_KEY,
    aws_secret_access_key=LEGACY_AWS_SECRET_ACCESS_KEY,
)


def _get_topic_arn_by_name(name):
    topics_res = sns.list_topics()
    topics = topics_res.get('Topics')
    topic = next((t for t in topics if name in t['TopicArn']), {})
    return topic.get('TopicArn')


def _publish_event(topic_name, subject, message):
    topic_arn = _get_topic_arn_by_name(topic_name)
    event_params = {
        'TopicArn': topic_arn,
        'Subject': subject,
        'Message': json.dumps(message),
    }

    logger.info(f'Publish event {event_params}')
    sns.publish(**event_params)


def send_user_invite(user_data, organization_name):
    USER_INVITE_TOPIC_NAME = f'UserInvitedToOrganization-{ENV}'
    message = {
        **user_data,
        'temporaryPassword': user_data.get('temporary_password'),
        'organizationName': organization_name,
    }

    _publish_event(USER_INVITE_TOPIC_NAME, 'UserInvitedToOrganization', message)
