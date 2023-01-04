import json
from pathlib import Path
from typing import Dict

from httmock import HTTMock, urlmatch

AUDIT_NOTIFICATIONS = "Audit Notifications"

UNEXPECTED_API_OPERATION = 'Unexpected operation for Slack fake api'


def fake_slack_api():
    return HTTMock(fake_slack_services)


def load_response(filename):
    with open(Path(__file__).parent / filename, 'r') as file:
        return file.read()


@urlmatch(netloc='slack.com')
def fake_slack_services(url, request):
    if 'oauth.v2.access' in url.path:
        return load_response('raw_access_token_response.json')
    elif 'users.list' in url.path:
        return load_response('raw_users_response.json')
    elif 'conversations.list' in url.path:
        return load_response('raw_conversations_response.json')
    elif 'chat.postMessage' in url.path:
        return load_response('raw_conversations_response.json')
    raise ValueError(UNEXPECTED_API_OPERATION)


def get_notification_preferences() -> Dict:
    return json.loads(load_response('notification_preferences_response.json'))


SLACK_CONFIGURATION_STATE = {
    "channels": [
        {
            "id": "C02ETMGB9HU",
            "name": "random",
            "is_im": False,
            "is_group": False,
            "is_channel": True,
            "is_private": False,
        },
        {
            "id": "C02F0E07EG2",
            "name": "general",
            "is_im": False,
            "is_group": False,
            "is_channel": True,
            "is_private": False,
        },
        {
            "id": "C02FD3E6PHP",
            "name": "slack-integration",
            "is_im": False,
            "is_group": False,
            "is_channel": True,
            "is_private": False,
        },
    ],
    "settings": {
        "channels": [
            {
                "id": "C02ETMGB9HU",
                "isIm": False,
                "name": "random",
                "isGroup": False,
                "isChannel": True,
                "isPrivate": False,
                "__typename": "SlackChannelType",
            },
            {
                "id": "C02F0E07EG2",
                "isIm": False,
                "name": "general",
                "isGroup": False,
                "isChannel": True,
                "isPrivate": False,
                "__typename": "SlackChannelType",
            },
            {
                "id": "C02FD3E6PHP",
                "isIm": False,
                "name": "slack-integration",
                "isGroup": False,
                "isChannel": True,
                "isPrivate": False,
                "__typename": "SlackChannelType",
            },
        ],
        "selectedChannel": "C02FD3E6PHP",
        "notificationPreferences": [
            {
                "type": "AUDIT_INITIATED",
                "channel": "C02FD3E6PHP",
                "isEnable": True,
                "description": "When an Audit has been initiated",
                "notificationTitle": AUDIT_NOTIFICATIONS,
            },
            {
                "type": "DRAFT_REPORT_AVAILABLE",
                "channel": "C02FD3E6PHP",
                "isEnable": True,
                "description": "When a new Audit Draft Report is available for review",
                "notificationTitle": AUDIT_NOTIFICATIONS,
            },
            {
                "type": "AUDIT_COMPLETE",
                "channel": "C02FD3E6PHP",
                "isEnable": True,
                "description": "When an Audit has been completed",
                "notificationTitle": AUDIT_NOTIFICATIONS,
            },
            {
                "type": "MENTION",
                "channel": "C02FD3E6PHP",
                "isEnable": True,
                "showTitle": "true",
                "description": "A user has been mentioned in a comment",
                "notificationTitle": "Comment Notifications",
            },
            {
                "type": "REPLY",
                "channel": "C02FD3E6PHP",
                "isEnable": True,
                "description": (
                    "There is a new reply to a comment you have made or are following"
                ),
                "notificationTitle": "Comment Notifications",
            },
            {
                "type": "VENDOR_DISCOVERY",
                "channel": "C02FD3E6PHP",
                "isEnable": True,
                "showTitle": "true",
                "description": "When a new Vendor is discovered",
                "notificationTitle": "Discovery Notifications",
            },
            {
                "type": "PEOPLE_DISCOVERY",
                "channel": "C02FD3E6PHP",
                "isEnable": True,
                "description": "When new People are discovered",
                "notificationTitle": "Discovery Notifications",
            },
            {
                "type": "NEW_ASSIGNMENT",
                "channel": "C02FD3E6PHP",
                "isEnable": True,
                "description": "When users have been assigned a New Task",
                "notificationTitle": "Tasks & Reminders",
            },
            {
                "type": "TRAINING_REMINDER",
                "channel": "C02FD3E6PHP",
                "isEnable": True,
                "showTitle": "true",
                "description": "When users have outstanding Training to complete",
                "notificationTitle": "Tasks & Reminders",
            },
        ],
    },
    "launchedOauth": False,
    "last_successful_run": 1653425072.150784,
}
