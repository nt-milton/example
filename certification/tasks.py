import logging

from laika.utils.websocket import send_ws_message_to_group
from seeder.constants import CX_APP_ROOM
from user.models import User

logger = logging.getLogger(__name__)


def broadcast_frameworks_notification(info, organization_id: str):
    for user in User.objects.filter(role='Concierge'):
        logger.info(f'Send framework notification to: {user.email}')
        send_ws_message_to_group(
            room_id=CX_APP_ROOM,
            sender='Admin',
            receiver=user.email,
            logger=logger,
            event_type='FRAMEWORKS_UNLOCKED',
            payload=dict(
                type='update_frameworks',
                sender=info.context.user.email,
                display_message=f'Frameworks updated by {info.context.user}',
                organization_id=organization_id,
            ),
        )
