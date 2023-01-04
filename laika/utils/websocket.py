from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def send_ws_message_to_group(
    room_id, sender, receiver, logger, event_type=None, payload=None
):
    try:
        # Send an alert to group
        async_to_sync(get_channel_layer().group_send)(
            f'room_{room_id}',
            {
                'type': 'new_message',
                'receiver': receiver,
                'event_type': event_type,
                'payload': payload,
            },
        )
    except Exception:
        logger.error(
            f'Failed to send websocket message organization: {room_id} sender: {sender}'
        )


def send_message(info, event_type: str, logger, payload={}):
    send_ws_message_to_group(
        room_id=info.context.user.organization.id,
        sender=info.context.user.email,
        receiver=info.context.user.email,
        logger=logger,
        event_type=event_type,
        payload=payload,
    )
