from comment.mutations import (
    AddAuditorComment,
    AddAuditorReply,
    AddComment,
    AddCommentOrReply,
    AddReply,
    DeleteAuditorComment,
    DeleteAuditorReply,
    DeleteComment,
    DeleteReply,
    UpdateAuditorComment,
    UpdateAuditorCommentState,
    UpdateAuditorReply,
    UpdateComment,
    UpdateCommentState,
    UpdateReply,
)


class Mutation(object):
    delete_reply = DeleteReply.Field()
    add_reply = AddReply.Field()
    update_reply = UpdateReply.Field()
    update_comment = UpdateComment.Field()
    update_comment_state = UpdateCommentState.Field()
    delete_comment = DeleteComment.Field()
    add_comment = AddComment.Field()
    add_comment_or_reply = AddCommentOrReply.Field()
    add_auditor_comment = AddAuditorComment.Field()
    delete_auditor_comment = DeleteAuditorComment.Field()
    update_auditor_comment = UpdateAuditorComment.Field()
    add_auditor_reply = AddAuditorReply.Field()
    delete_auditor_reply = DeleteAuditorReply.Field()
    update_auditor_reply = UpdateAuditorReply.Field()
    update_auditor_comment_state = UpdateAuditorCommentState.Field()
