import logging
from datetime import datetime
from typing import Callable, Iterator, NamedTuple

from django.core.exceptions import PermissionDenied
from django.db import models

from alert.constants import ALERT_TYPES
from alert.models import Alert
from audit.models import Audit, DraftReportComment
from comment.constants import COMMENT_STATE
from comment.models import Mention, Reply
from comment.validators import (
    CONTROL,
    DRAFT_REPORT,
    EVIDENCE,
    POLICY,
    POPULATION,
    REQUIREMENT,
    TASK,
    comment_type,
    permission_validator,
)
from control.models import ControlComment
from fieldwork.models import (
    EvidenceComment,
    RequirementComment,
    create_evidence_mention_alerts,
    get_room_id_for_alerts,
)
from laika.utils.exceptions import ServiceException
from policy.models import PolicyComment
from population.models import PopulationComment
from program.models import TaskComment

logger = logging.getLogger('comment_utils')


def strip_comment_reply_content(content):
    return content.strip() if content else None


def validate_comment_content(content, user_email):
    if not content:
        logger.error(f'Trying to create a comment with empty contentuser {user_email}')
        raise ServiceException('Comment content cannot be empty')


def create_comment(user, input, model):
    content = strip_comment_reply_content(input.content)
    validate_comment_content(content=content, user_email=user.email)
    return model.objects.custom_create(
        owner=user,
        content=content,
        requirement_id=input.requirement_id,
        tagged_users=input.get('tagged_users'),
    )


def update_reply(user, reply_input):
    reply = Reply.objects.get(
        pk=reply_input.reply_id,
    )
    permission_validator(reply.parent).validate_change(user)
    if not reply.is_reply_owner(user):
        raise PermissionDenied

    reply.content = strip_comment_reply_content(reply_input.content)
    validate_comment_content(content=reply_input.content, user_email=user.email)
    reply.save()
    mentions = reply.add_mentions(reply_input.tagged_users)
    return reply, mentions


def delete_reply(user, reply_input):
    reply = Reply.objects.get(id=reply_input.reply_id, parent_id=reply_input.comment_id)
    permission_validator(reply.parent).validate_delete(user)
    if not reply.is_reply_owner(user):
        raise PermissionDenied

    reply.is_deleted = True
    reply.save()

    logger.info(f'Reply id {reply.id} was logical deleted')

    return reply


def update_comment_state_requirement(comment, user, new_state):
    comment_state = dict(COMMENT_STATE)
    is_new_state_valid = new_state in comment_state.values()

    if not is_new_state_valid:
        raise ServiceException('Invalid comment state')

    resolve_comment = new_state == comment_state['RESOLVED']

    comment.state = new_state
    comment.resolved_by = user if resolve_comment else None
    comment.resolved_at = datetime.now() if resolve_comment else None

    comment.save()

    return comment


def create_mention_alerts(
    mentions: list[Mention], alert_type=ALERT_TYPES['MENTION']
) -> Iterator[tuple[Mention, Alert]]:
    for mention in mentions:
        room_id = mention.user.organization.id
        alert = mention.create_mention_alert(room_id, alert_type)
        if alert:
            yield mention, alert


def create_program_mention_alerts(mentions: list[Mention]):
    for mention, alert in create_mention_alerts(mentions):
        alert.send_comment_task_alert_email(
            task_related=mention.get_mention_task_related()
        )


def create_control_mention_alerts(mentions: list[Mention]):
    reply_mentions = [mention for mention in mentions if mention.reply]
    create_control_types_mention_alerts(reply_mentions, ALERT_TYPES['CONTROL_REPLY'])

    comment_mentions = [
        mention for mention in mentions if mention.comment and not mention.reply
    ]
    create_control_types_mention_alerts(
        comment_mentions, ALERT_TYPES['CONTROL_MENTION']
    )


def create_control_types_mention_alerts(mentions: list[Mention], alert_type: str):
    for mention, alert in create_mention_alerts(mentions, alert_type):
        alert.send_comment_control_alert_email(
            control_related=mention.get_mention_control_related()
        )


def create_policy_mention_alerts(mentions: list[Mention]):
    reply_mentions = [
        mention
        for mention in mentions
        if mention.reply and not mentions[0].reply.parent.owner == mention.user
    ]
    create_policy_types_mention_alerts(reply_mentions, ALERT_TYPES['POLICY_REPLY'])

    comment_mentions = [
        mention
        for mention in mentions
        if mention.comment
        and not mention.reply
        and not mentions[0].comment.owner == mention.user
    ]
    create_policy_types_mention_alerts(comment_mentions, ALERT_TYPES['POLICY_MENTION'])


def create_policy_types_mention_alerts(mentions: list[Mention], alert_type: str):
    for mention, alert in create_mention_alerts(mentions, alert_type):
        alert.send_comment_policy_alert_email(
            policy_message_data=mention.get_mention_policy_message_data()
        )


ALERT_BY_APP: dict[str, Callable] = {
    TASK: create_program_mention_alerts,
    CONTROL: create_control_mention_alerts,
    POLICY: create_policy_mention_alerts,
    EVIDENCE: create_evidence_mention_alerts,
}


def handle_alert_mentions(comment, mentions):
    c_type = comment_type(comment)
    handler = ALERT_BY_APP.get(c_type)
    if handler:
        handler(mentions)


def notify_add_control_reply(alert, reply):
    control_related = {
        'control': reply.parent.control.first(),
        'message_content': reply.content,
        'message_owner': reply.owner_name,
    }
    alert.send_comment_control_alert_email(control_related=control_related)


def notify_add_policy_reply(alert, reply):
    policy_message_data = {
        'policy': reply.parent.policies.first(),
        'message_content': reply.content,
        'message_owner': reply.owner_name,
    }

    alert.send_comment_policy_alert_email(policy_message_data=policy_message_data)


def notify_add_program_reply(alert, reply):
    task_related = {
        'task': reply.parent.task.first().task,
        'message_content': reply.content,
        'message_owner': reply.owner_name,
    }
    alert.send_comment_task_alert_email(task_related=task_related)


def notify_add_evidence_reply(alert, reply):
    comment = reply.parent
    evidence = comment.evidence_comments.first().evidence
    alert.send_evidence_comment_alert_email(evidence=evidence, content=reply.content)


ADD_REPLY_NOTIFICATION: dict[str, tuple[str, Callable]] = {
    TASK: (ALERT_TYPES['REPLY'], notify_add_program_reply),
    CONTROL: (ALERT_TYPES['CONTROL_REPLY'], notify_add_control_reply),
    POLICY: (ALERT_TYPES['POLICY_REPLY'], notify_add_policy_reply),
    EVIDENCE: (ALERT_TYPES['EVIDENCE_REPLY'], notify_add_evidence_reply),
}


def send_add_reply_notification(reply):
    c_type = comment_type(reply.parent)
    room_id = get_room_id_for_alerts(reply.parent.owner)
    alert_type, add_reply_notification = ADD_REPLY_NOTIFICATION[c_type]
    alert = reply.create_reply_alert(room_id, alert_type)
    if alert:
        add_reply_notification(alert, reply)


def notify_add_reply(reply, input):
    c_type = comment_type(reply.parent)
    if c_type in ADD_REPLY_NOTIFICATION:
        send_add_reply_notification(reply)
        mentions = reply.add_mentions(input.tagged_users)
        handle_alert_mentions(reply.parent, mentions)


def notify_task_comment_resolved(comment, user):
    if comment.state == 'RESOLVED' and user != comment.owner:
        room_id = user.organization.id
        task_related = {
            'task': comment.task.first().task,
            'message_content': comment.content,
            'message_owner': comment.owner_name,
        }
        alert = comment.create_resolve_comment_alert(
            room_id=room_id, task_related=task_related
        )
        alert.send_comment_task_alert_email(task_related)


def draft_report_comment_params(info, input):
    audit = Audit.objects.get(
        id=input.object_id, organization=info.context.user.organization
    )
    return {'page': input.get('page'), 'audit_id': audit.id}


def evidence_comment_params(info, input):
    return {'pool': input.pool, 'evidence_id': input.object_id}


def requirement_comment_params(info, input):
    return {'requirement_id': input.object_id}


def task_comment_params(info, input):
    return {'organization': info.context.user.organization, 'task_id': input.object_id}


def control_comment_params(info, input):
    return {
        'organization': info.context.user.organization,
        'control_id': input.object_id,
    }


def policy_comment_params(info, input):
    return {
        'organization': info.context.user.organization,
        'policy_id': input.object_id,
        'action_id': input.action_id,
    }


def population_comment_params(info, input):
    return {'pool': input.pool, 'population_id': input.object_id}


class CommentMetadata(NamedTuple):
    model: models.Model
    app: str
    field_id: str
    add_comment_param: Callable


COMMENT_MODEL: dict[str, CommentMetadata] = {
    CONTROL: CommentMetadata(
        ControlComment, 'control', 'control_id', control_comment_params
    ),
    POLICY: CommentMetadata(
        PolicyComment, 'policy', 'policy_id', policy_comment_params
    ),
    TASK: CommentMetadata(TaskComment, 'task', 'task_id', task_comment_params),
    DRAFT_REPORT: CommentMetadata(
        DraftReportComment, 'draft report', 'audit_id', draft_report_comment_params
    ),
    EVIDENCE: CommentMetadata(
        EvidenceComment, 'evidence', 'evidence_id', evidence_comment_params
    ),
    POPULATION: CommentMetadata(
        PopulationComment, 'population', 'population_id', population_comment_params
    ),
    REQUIREMENT: CommentMetadata(
        RequirementComment, 'requirement', 'requirement_id', requirement_comment_params
    ),
}


def get_comment_model(comment_input):
    comment_relation, app, id_param, _ = COMMENT_MODEL.get(comment_input.object_type)
    comment_model = comment_relation.objects.filter(
        **{id_param: comment_input.object_id}, comment_id=comment_input.comment_id
    ).first()
    if not comment_model:
        logger.error(
            'Comment does not exist. Unable to perform operation'
            f' for comment: {comment_input.comment_id}'
            f' with {app}: {comment_input.object_id}'
        )
        raise ValueError(
            f'Comment {comment_input.comment_id} not found. Unable to perform operation'
        )
    return comment_model


def add_comment(info, input):
    content = strip_comment_reply_content(input.content)
    validate_comment_content(content=content, user_email=info.context.user.email)
    comment_metadata = COMMENT_MODEL.get(input.object_type)
    comment_relation = comment_metadata.model
    comment = comment_relation.objects.custom_create(
        owner=info.context.user,
        content=content,
        tagged_users=input.get('tagged_users'),
        **comment_metadata.add_comment_param(info, input),
    )
    return comment


def delete_comment(info, input):
    owner = info.context.user
    comment_model = get_comment_model(input)
    comment = comment_model.comment
    if owner != comment.owner:
        raise PermissionDenied
    comment.is_deleted = True
    comment.save()

    logger.info(f'Comment id {input.comment_id} was logical deleted')
    return comment


def update_comment(user, comment_input):
    comment_model = get_comment_model(comment_input)
    comment = comment_model.comment
    c_type = comment_type(comment)
    content = strip_comment_reply_content(comment_input.get('content'))
    if not comment.is_comment_owner(user):
        raise PermissionDenied
    validate_comment_content(content=content, user_email=user.email)
    if c_type is DRAFT_REPORT:
        comment_model.update(user, comment_input)
    else:
        comment.update(user, comment_input)
    mentions = comment.mentions.all()
    handle_alert_mentions(comment, mentions)
    return comment


def add_reply(user, reply_input):
    comment_model = get_comment_model(reply_input)
    comment = comment_model.comment
    content = strip_comment_reply_content(reply_input.content)

    validate_comment_content(content=content, user_email=user.email)

    reply = Reply.objects.create(owner=user, content=content, parent=comment)
    notify_add_reply(reply, reply_input)
    comment.replies.add(reply)
    return reply


def update_comment_state(user, comment_input):
    comment_model = get_comment_model(comment_input)
    comment = comment_model.comment
    c_type = comment_type(comment)
    comment.update(user, comment_input)
    if c_type is TASK:
        notify_task_comment_resolved(comment, user)
    return comment
