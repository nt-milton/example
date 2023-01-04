import logging
from datetime import datetime

from django.db import models

from alert.constants import ALERT_TYPES
from alert.models import Alert
from comment.constants import COMMENT_STATE
from comment.launchpad import launchpad_mapper
from laika.aws.ses import send_email
from program.utils.alerts import create_alert
from search.search import launchpad_model
from user.models import User

logger = logging.getLogger('alerts')


def create_mentions(
    tagged_users,
    entity,
    relation_type='comment',
):
    param = {'comment': entity} if relation_type == 'comment' else {'reply': entity}
    mentions_list = []
    for tagged_users_email in tagged_users or []:
        tagged_user = User.objects.get(email=tagged_users_email)
        mention_exists = Mention.objects.filter(**param, user=tagged_user).exists()

        if mention_exists:
            continue

        mention = Mention(**param, user=tagged_user)
        mention.save()
        mentions_list.append(mention)
    return mentions_list


@launchpad_model(context='comment', mapper=launchpad_mapper)
class Comment(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(
        User,
        related_name='user_comments',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    # This is in case the user is deleted we still need to display
    # the name in the comment
    owner_name = models.CharField(max_length=100, blank=True)
    content = models.TextField()
    resolved_by = models.ForeignKey(
        User,
        related_name='comment_resolver',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    is_deleted = models.BooleanField(default=False)
    state = models.CharField(
        max_length=25, choices=COMMENT_STATE, blank=True, default='UNRESOLVED'
    )
    # OnlyOffice uses this as identifier to tract replies
    action_id = models.CharField(max_length=25, blank=True)

    def __str__(self):
        return self.content

    def add_mentions(self, tagged_users):
        return create_mentions(tagged_users, self, 'comment')

    def create_resolve_comment_alert(self, room_id, **kwargs):
        sender = self.resolved_by
        return create_alert(
            room_id=room_id,
            sender=sender,
            receiver=self.owner,
            alert_type=ALERT_TYPES['RESOLVE'],
            alert_related_model=CommentAlert,
            alert_related_object={'comment': self},
            **kwargs
        )

    def is_comment_owner(self, user):
        return self.owner == user

    def update(self, user, input):
        content_input = input.get('content')
        content = content_input.strip() if content_input else None
        comment_state = dict(COMMENT_STATE)

        if content:
            self.content = content
        if input.get('state') == comment_state['RESOLVED']:
            self.state = comment_state['RESOLVED']
            self.resolved_by = user
            self.resolved_at = datetime.now()
        elif input.get('state') == comment_state['UNRESOLVED']:
            self.state = comment_state['UNRESOLVED']
            self.resolved_by = None
            self.resolved_at = None

        self.save()
        if input.get('tagged_users'):
            self.add_mentions(input.tagged_users)
        return self

    def save(self, *args, **kwargs):
        if self.owner:
            self.owner_name = self.owner.get_full_name().title()

        super(Comment, self).save(*args, **kwargs)


class Reply(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    owner = models.ForeignKey(
        User, related_name='replies', on_delete=models.SET_NULL, null=True, blank=True
    )
    # This is in case the user is deleted we still need to display
    # the name in the reply
    owner_name = models.CharField(max_length=100, blank=True)
    content = models.TextField()
    parent = models.ForeignKey(
        Comment, related_name='replies', on_delete=models.CASCADE
    )
    is_deleted = models.BooleanField(default=False)

    def add_mentions(self, tagged_users):
        return create_mentions(tagged_users, self, 'reply')

    def save(self, *args, **kwargs):
        if self.owner:
            self.owner_name = self.owner.get_full_name().title()
        super(Reply, self).save()

    def create_reply_alert(self, room_id, alert_type=ALERT_TYPES['REPLY']):
        if self.owner != self.parent.owner:
            return create_alert(
                room_id=room_id,
                sender=self.owner,
                receiver=self.parent.owner,
                alert_type=alert_type,
                alert_related_model=ReplyAlert,
                alert_related_object={'reply': self},
            )

    def is_reply_owner(self, user):
        return self.owner == user

    def update(self, input):
        content_input = input.get('content')
        content = content_input.strip() if content_input else None
        if content:
            self.content = content
            self.save()

        self.add_mentions(input.tagged_users)
        return self


class Mention(models.Model):
    user = models.ForeignKey(User, related_name='mentions', on_delete=models.CASCADE)
    comment = models.ForeignKey(
        Comment,
        related_name='mentions',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    reply = models.ForeignKey(
        Reply, related_name='mentions', on_delete=models.CASCADE, null=True, blank=True
    )

    def get_mention_task_related(self):
        if self.reply:
            return {
                'task': self.reply.parent.task.first().task,
                'message_content': self.reply.content,
                'message_owner': self.reply.owner_name,
            }
        elif self.comment:
            return {
                'task': self.comment.task.first().task,
                'message_content': self.comment.content,
                'message_owner': self.comment.owner_name,
            }

    def get_mention_control_related(self):
        if self.reply:
            return {
                'control': self.reply.parent.control_comments.first().control,
                'message_content': self.reply.content,
                'message_owner': self.reply.owner_name,
            }
        elif self.comment:
            return {
                'control': self.comment.control_comments.first().control,
                'message_content': self.comment.content,
                'message_owner': self.comment.owner_name,
            }

    def get_mention_policy_message_data(self):
        if self.reply:
            return {
                'policy': self.reply.parent.policy_comments.first().policy,
                'message_content': self.reply.content,
                'message_owner': self.reply.owner_name,
            }
        elif self.comment:
            return {
                'policy': self.comment.policy_comments.first().policy,
                'message_content': self.comment.content,
                'message_owner': self.comment.owner_name,
            }

    def create_mention_alert(self, room_id, alert_type=ALERT_TYPES['MENTION']):
        # After creating a mention create an alert
        sender = self.reply.owner if self.reply else self.comment.owner
        receiver = self.user
        if sender != receiver:
            if self.reply:
                return create_alert(
                    room_id=room_id,
                    sender=sender,
                    receiver=receiver,
                    alert_type=alert_type,
                    alert_related_model=ReplyAlert,
                    alert_related_object={'reply': self.reply},
                )
            elif self.comment:
                return create_alert(
                    room_id=room_id,
                    sender=sender,
                    receiver=receiver,
                    alert_type=alert_type,
                    alert_related_model=CommentAlert,
                    alert_related_object={'comment': self.comment},
                )

    def send_mention_email(self, context):
        model_related = self.comment if self.comment else self.reply
        mention_alert = {
            'message_owner': model_related.owner_name,
            'created_at': model_related.created_at,
            'sender_name': model_related.owner_name,
            'content': model_related.content,
        }
        context['template_context']['alerts'] = [mention_alert]
        send_email(
            subject=context.get('subject'),
            from_email=context.get('from_email'),
            to=[context.get('to')],
            template=context.get('template'),
            template_context=context.get('template_context'),
        )

    def save(self, *args, **kwargs):
        if not self.comment and not self.reply:
            raise ValueError('Missing comment and reply for user mention')

        super(Mention, self).save()


class CommentAlert(models.Model):
    alert = models.ForeignKey(
        Alert, related_name='comment_alert', on_delete=models.CASCADE
    )
    comment = models.ForeignKey(
        Comment,
        related_name='alerts',
        on_delete=models.CASCADE,
    )


class ReplyAlert(models.Model):
    alert = models.ForeignKey(
        Alert, related_name='reply_alert', on_delete=models.CASCADE
    )
    reply = models.ForeignKey(
        Reply,
        related_name='alerts',
        on_delete=models.CASCADE,
    )
