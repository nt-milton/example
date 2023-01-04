import json
import logging

from asgiref.sync import async_to_sync
from channels.exceptions import DenyConnection
from channels.generic.websocket import WebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from laika.constants import WSEventTypes

logger = logging.getLogger('web_consumer')


def _should_deny_connection(user):
    if not user:
        logger.warning('Request to web sockets without user')
        return True
    if isinstance(user, AnonymousUser):
        logger.warning('Request to web sockets by Anonymous user')
        return True
    if not user.is_active:
        logger.warning(f'Request to web sockets by Inactive user {user}')
        return True
    return False


class AlertWebConsumer(WebsocketConsumer):
    groups = ["broadcast"]

    def __init__(self):
        self.room_name = ''
        self.email = ''

    def connect(self):
        # These parameters are taken from the URL
        room_id = self.scope['url_route']['kwargs']['room_id']
        email = self.scope['url_route']['kwargs']['email']

        user = self.scope['user']

        # Stored in class to be used in the other websocket methods
        room_name = f'room_{room_id}'
        self.room_name = room_name
        self.email = email

        if _should_deny_connection(user):
            raise DenyConnection("Invalid User.")

        # self.channel_name is assigned on the settings for CHANNEL_LAYERS
        async_to_sync(self.channel_layer.group_add)(room_name, self.channel_name)

        # Sends a reply saying that the websocket connection was accepted
        self.accept()

        logger.info(f'Web Consumer CONNECT room: {room_id} email: {email}')

    def new_message(self, event):
        logger.info(f'New message in "new_message" event {event} ')
        # Validate the receiver
        if self.email == event['receiver']:
            event_type = event.get('event_type')
            self.send(
                text_data=json.dumps(
                    {
                        'event': event_type if event_type else WSEventTypes.ALERT.value,
                        'payload': event.get('payload', ''),
                    }
                )
            )

    # Method to handle the client disconnection
    def disconnect(self, event):
        logger.info(
            f'Web Consumer DISCONNECT room: {self.room_name} email: {self.email}'
        )
        # Leave room group
        async_to_sync(self.channel_layer.group_discard)(
            self.room_name, self.channel_name
        )
