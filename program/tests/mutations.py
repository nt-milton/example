ADD_TASK_COMMENT = '''
    mutation addTaskComment($input: AddTaskCommentInput!) {
        addTaskComment(input: $input) {
          commentId
        }
    }
'''

ADD_TASK_REPLY = '''
    mutation addTaskReply($input: AddTaskReplyInput!) {
        addTaskReply(input: $input) {
          replyId
        }
    }
'''

UPDATE_TASK_COMMENT = '''
    mutation updateTaskComment($input: UpdateTaskCommentInput!) {
      updateTaskComment(input: $input) {
        commentId
      }
    }
'''


UPDATE_COMMENT_STATE = '''
    mutation updateCommentState($input: UpdateCommentStateInput!) {
        updateCommentState(input: $input) {
          comment{
            id
          }
        }
    }
'''

UPDATE_PROGRAM = '''
        mutation updateProgram($input: UpdateProgramInput!) {
            updateProgram(input: $input) {
              program {
                id
                programLead {
                  id
                  email
                  firstName
                  lastName
                }
              }
            }
        }
    '''

UPDATE_SUBTASK_STATUS = '''
        mutation updateSubTaskStatus($input: UpdateSubTaskStatusInput!) {
            updateSubtaskStatus(input: $input) {
                subtask {
                    id
                }
            }
        }
    '''

UPDATE_SUBTASK_DUE_DATE = '''
        mutation updateSubTaskDueDate($input: UpdateSubTaskDueDateInput!) {
            updateSubtaskDueDate(input: $input) {
                subtask {
                    id
                }
            }
        }
    '''

UPDATE_SUBTASK_ASSIGNEE = '''
        mutation updateSubTaskAssignee($input: UpdateSubTaskAssigneeInput!) {
            updateSubtaskAssignee(input: $input) {
                subtask {
                    id
                }
            }
        }
    '''


UPDATE_ALERT_VIEWED = '''
    mutation updateAlertViewed {
      updateAlertViewed {
        success
      }
    }
'''

CREATE_SUBTASK_WITH_ASSIGNEE = '''
    mutation createSubTask($input: CreateSubTaskInput!) {
      createSubtask(input: $input) {
          subtask {
            id
            text
            group
          }
      }
    }
'''

UPDATE_SUBTASK = '''
    mutation updateSubTask($input: UpdateSubTaskInput!) {
      updateSubtask(input: $input) {
          subtask {
                id
                text
                group
                assignee {
                    email
                }
          }
      }
    }
'''

ADD_EVIDENCE_ATTACHMENT = '''
  mutation addEvidenceAttachment($input: AddEvidenceAttachmentInput!) {
    addEvidenceAttachment(input: $input) {
      documentIds
    }
  }
'''

ADD_SUBTASK_EVIDENCE = '''
  mutation addSubTaskEvidence($input: AddSubTaskEvidenceInput!) {
    addSubtaskEvidence(input: $input) {
      documentIds
    }
  }
'''
