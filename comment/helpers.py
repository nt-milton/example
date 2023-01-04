import logging

from .models import Comment, Reply

logger = logging.getLogger('comments')


def get_comment_by_id(comment_id):
    try:
        return Comment.objects.get(id=comment_id)
    except Comment.DoesNotExist:
        logger.warning(f'Comment with an id: {comment_id} not found')
        return None


def get_reply_by_id(reply_id):
    try:
        return Reply.objects.get(id=reply_id)
    except Reply.DoesNotExist:
        logger.warning(f'Reply with an id: {reply_id} not found')
        return None
