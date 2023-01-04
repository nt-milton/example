ADD_COMMENT = '''
    mutation addComment($input: AddCommentInput!) {
        addComment(input: $input) {
          comment {
            id
          }
        }
    }
'''

ADD_COMMENT_OR_REPLY = '''
    mutation addCommentOrReply($input: AddCommentOrReplyInput!) {
        addCommentOrReply(input: $input) {
            reply {
              id
            }
        }
    }
'''

DELETE_REPLY = '''
  mutation deleteReply($input: DeleteReplyInput!) {
    deleteReply(input: $input) {
      replyId
    }
  }
'''

UPDATE_REPLY = '''
  mutation updateReply($input: UpdateReplyInput!) {
    updateReply(input: $input) {
      replyId
    }
  }
'''

ADD_REPLY = '''
    mutation addReply($input: AddReplyInput!) {
        addReply(input: $input) {
          reply {
            id
          }
        }
    }
'''
