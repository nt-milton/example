import logging

import graphene

from comment.inputs import (
    AddCommentInput,
    AddCommentOrReplyInput,
    AddReplyInput,
    DeleteCommentInput,
    DeleteReplyInput,
    UpdateCommentInput,
    UpdateCommentStateInput,
    UpdateReplyInput,
)
from comment.models import Comment
from comment.types import BaseCommentType
from comment.utils import (
    add_comment,
    add_reply,
    delete_comment,
    delete_reply,
    handle_alert_mentions,
    update_comment,
    update_comment_state,
    update_reply,
)
from laika.decorators import audit_service, laika_service

logger = logging.getLogger('comment_mutations')


class AddCommentOrReply(graphene.Mutation):
    class Arguments:
        input = AddCommentOrReplyInput(required=True)

    comment = graphene.Field(BaseCommentType)
    reply = graphene.Field(BaseCommentType)

    @laika_service(
        permission='comment.add_comment',
        exception_msg='Failed to add comment or reply. Please try again.',
        revision_name='Add comment',
    )
    def mutate(self, info, input):
        # This mutation is required because onlyOffice handles replies and
        # comment as 1 item, so we need to identify comments with the action_id
        current_comment = Comment.objects.filter(action_id=input.action_id).first()

        if current_comment is None:
            comment = add_comment(info, input)
            return AddComment(comment=comment)
        else:
            input.comment_id = current_comment.id
            owner = info.context.user
            reply = add_reply(user=owner, reply_input=input)
            return AddReply(reply=reply)


class AddComment(graphene.Mutation):
    class Arguments:
        input = AddCommentInput(required=True)

    comment = graphene.Field(BaseCommentType)

    @laika_service(
        permission='comment.add_comment',
        exception_msg='Failed to add comment. Please try again.',
        revision_name='Add comment',
    )
    def mutate(self, info, input):
        comment = add_comment(info, input)
        return AddComment(comment=comment)


class DeleteComment(graphene.Mutation):
    class Arguments:
        input = DeleteCommentInput(required=True)

    comment = graphene.Field(BaseCommentType)

    @laika_service(
        permission='comment.delete_comment',
        exception_msg='Failed to delete comment. Please try again.',
        revision_name='Soft delete comment',
    )
    def mutate(self, info, input):
        comment = delete_comment(info, input)
        return DeleteComment(comment=comment)


class DeleteReply(graphene.Mutation):
    class Arguments:
        input = DeleteReplyInput(required=True)

    reply_id = graphene.String()

    @laika_service(
        permission='comment.delete_reply',
        exception_msg='Failed to delete reply. Please try again.',
        revision_name='Soft delete reply',
    )
    def mutate(self, info, input):
        user = info.context.user
        reply = delete_reply(user=user, reply_input=input)
        return DeleteReply(reply_id=reply.id)


class AddReply(graphene.Mutation):
    class Arguments:
        input = AddReplyInput(required=True)

    reply = graphene.Field(BaseCommentType)

    @laika_service(
        permission='comment.add_reply',
        exception_msg='Failed to add reply. Please try again.',
        revision_name='Add reply',
    )
    def mutate(self, info, input):
        owner = info.context.user
        reply = add_reply(user=owner, reply_input=input)
        return AddReply(reply=reply)


class UpdateReply(graphene.Mutation):
    class Arguments:
        input = UpdateReplyInput(required=True)

    reply_id = graphene.String()

    @laika_service(
        permission='comment.change_reply',
        exception_msg='Failed to update reply. Please try again',
        revision_name='Soft update reply',
    )
    def mutate(self, info, input):
        user = info.context.user
        reply, mentions = update_reply(user, reply_input=input)
        handle_alert_mentions(reply.parent, mentions)
        return UpdateReply(reply_id=reply.id)


class UpdateComment(graphene.Mutation):
    class Arguments:
        input = UpdateCommentInput(required=True)

    comment = graphene.Field(BaseCommentType)

    @laika_service(
        permission='comment.change_comment',
        exception_msg='Failed to update comment. Please try again.',
        revision_name='Change comment',
    )
    def mutate(self, info, input):
        user = info.context.user
        comment = update_comment(user, comment_input=input)
        return UpdateComment(comment=comment)


class UpdateCommentState(graphene.Mutation):
    class Arguments:
        input = UpdateCommentStateInput(required=True)

    comment = graphene.Field(BaseCommentType)

    @laika_service(
        permission='comment.change_comment',
        exception_msg='Failed to update comment state. Please try again.',
        revision_name='Change comment state',
    )
    def mutate(self, info, input):
        user = info.context.user
        comment = update_comment_state(user=user, comment_input=input)
        return UpdateCommentState(comment=comment)


class AddAuditorComment(graphene.Mutation):
    class Arguments:
        input = AddCommentInput(required=True)

    comment = graphene.Field(BaseCommentType)

    @audit_service(
        permission='comment.add_comment',
        exception_msg='Failed to add comment. Please try again.',
        revision_name='Add comment',
    )
    def mutate(self, info, input):
        comment = add_comment(info, input)
        return AddAuditorComment(comment=comment)


class DeleteAuditorComment(graphene.Mutation):
    class Arguments:
        input = DeleteCommentInput(required=True)

    comment = graphene.Field(BaseCommentType)

    @audit_service(
        permission='comment.delete_comment',
        exception_msg='Failed to delete comment. Please try again.',
        revision_name='Soft delete comment',
    )
    def mutate(self, info, input):
        comment = delete_comment(info, input)
        return DeleteAuditorComment(comment=comment)


class UpdateAuditorComment(graphene.Mutation):
    class Arguments:
        input = UpdateCommentInput(required=True)

    comment = graphene.Field(BaseCommentType)

    @audit_service(
        permission='comment.change_comment',
        exception_msg='Failed to update comment. Please try again.',
        revision_name='Change comment',
    )
    def mutate(self, info, input):
        user = info.context.user
        comment = update_comment(user, comment_input=input)
        return UpdateAuditorComment(comment=comment)


class AddAuditorReply(graphene.Mutation):
    class Arguments:
        input = AddReplyInput(required=True)

    reply = graphene.Field(BaseCommentType)

    @audit_service(
        permission='comment.add_reply',
        exception_msg='Failed to add reply. Please try again.',
        revision_name='Add reply',
    )
    def mutate(self, info, input):
        owner = info.context.user
        reply = add_reply(user=owner, reply_input=input)
        return AddAuditorReply(reply=reply)


class DeleteAuditorReply(graphene.Mutation):
    class Arguments:
        input = DeleteReplyInput(required=True)

    reply = graphene.Field(BaseCommentType)

    @audit_service(
        permission='comment.delete_reply',
        exception_msg='Failed to delete reply. Please try again.',
        revision_name='Soft delete reply',
    )
    def mutate(self, info, input):
        user = info.context.user
        reply = delete_reply(user, reply_input=input)
        return DeleteAuditorReply(reply=reply)


class UpdateAuditorReply(graphene.Mutation):
    class Arguments:
        input = UpdateReplyInput(required=True)

    reply = graphene.Field(BaseCommentType)

    @audit_service(
        permission='comment.change_reply',
        exception_msg='Failed to update reply. Please try again',
        revision_name='Soft update reply',
    )
    def mutate(self, info, input):
        user = info.context.user
        reply, mentions = update_reply(user, reply_input=input)
        handle_alert_mentions(reply.parent, mentions)
        return UpdateAuditorReply(reply=reply)


class UpdateAuditorCommentState(graphene.Mutation):
    class Arguments:
        input = UpdateCommentStateInput(required=True)

    comment = graphene.Field(BaseCommentType)

    @audit_service(
        permission='comment.change_comment',
        exception_msg='Failed to update comment state. Please try again.',
        revision_name='Change comment state',
    )
    def mutate(self, info, input):
        user = info.context.user
        comment = update_comment_state(user=user, comment_input=input)
        return UpdateAuditorCommentState(comment=comment)
