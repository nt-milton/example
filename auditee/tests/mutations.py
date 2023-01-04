UPDATE_EVIDENCE_LAIKA_REVIEWED = '''
    mutation
        updateAuditeeEvidenceLaikaReviewed(
            $input: UpdateEvidenceLaikaReviewedInput!){
          updateAuditeeEvidenceLaikaReviewed(input: $input){
           ids
          }
        }
'''

ASSIGN_EVIDENCE = '''
    mutation assignAuditeeEvidence($input: AssignEvidenceInput!){
      assignAuditeeEvidence(input: $input){
       ids
      }
    }
'''

CREATE_EVIDENCE_COMMENT = '''
        mutation createAuditeeEvidenceComment(
          $input: CreateEvidenceCommentInput!) {
            createAuditeeEvidenceComment(input: $input) {
                commentId
            }
        }
    '''

CREATE_EVIDENCE_REPLY = '''
        mutation createAuditeeEvidenceReply(
            $input: CreateEvidenceReplyInput!) {
          createAuditeeEvidenceReply(input: $input) {
            replyId
          }
        }
    '''


UPDATE_EVIDENCE_COMMENT = '''
        mutation updateAuditeeEvidenceComment(
            $input: UpdateEvidenceCommentInput!) {
            updateAuditeeEvidenceComment(input: $input) {
                commentId
            }
        }
    '''


RUN_FETCH_EVIDENCE = '''
    mutation runFetchEvidence($input: RunFetchEvidenceInput!) {
      runFetchEvidence(input: $input) {
        auditId
      }
    }
  '''

ASSIGN_TESTER_EVIDENCE = '''
    mutation assignAuditeeTesterEvidence($input: AssignEvidenceInput!) {
      assignAuditeeTesterEvidence(input: $input) {
        success
      }
    }
'''

UPDATE_EVIDENCE_STATUS = '''
        mutation updateAuditeeEvidenceStatus(
            $input: UpdateEvidenceStatusInput!){
            updateAuditeeEvidenceStatus(input:$input){
                updated
            }
        }
    '''

ADD_EVIDENCE_ATTACHMENT = '''
  mutation addAuditeeEvidenceAttachment($input: AddEvidenceAttachmentInput!) {
    addAuditeeEvidenceAttachment(input: $input) {
      documentIds
      monitorsError {
        message
      }
    }
  }
'''

DELETE_EVIDENCE_ATTACHMENT = '''
        mutation
        deleteAuditeeEvidenceAttachment(
            $input: DeleteEvidenceAttachmentInput!) {
            deleteAuditeeEvidenceAttachment(input: $input) {
                attachmentId
            }
        }
    '''

DELETE_AUDITEE_ALL_EVIDENCE_ATTACHMENTS = '''
        mutation
        deleteAuditeeAllEvidenceAttachments(
            $input: DeleteAllEvidenceAttachmentInput!) {
            deleteAuditeeAllEvidenceAttachments(input: $input) {
                evidence {
                  attachments {
                    id
                    name
                    description
                    createdAt
                  }
                }
            }
        }
    '''

UPDATE_EVIDENCE = '''
        mutation updateAuditeeEvidence($input: UpdateEvidenceInput!){
            updateAuditeeEvidence(input:$input){
                updated
            }
        }
    '''

CREATE_DRAFT_REPORT_COMMENT = '''
        mutation createAuditeeDraftReportComment(
          $input: CreateDraftReportCommentInput!) {
            createAuditeeDraftReportComment(input: $input) {
                draftReportComment {
                    comment {
                        id,
                        content
                    },
                    page
                }
            }
        }
    '''

UPDATE_DRAFT_REPORT_COMMENT = '''
        mutation updateAuditeeDraftReportComment(
          $input: UpdateDraftReportCommentInput!) {
            updateAuditeeDraftReportComment(input: $input) {
                draftReportComment {
                    comment {
                        id,
                        content,
                        state
                    },
                    page
                }
            }
        }
    '''

UPDATE_DRAFT_REPORT_COMMENT_STATE = '''
        mutation updateAuditeeDraftReportCommentState(
          $input: UpdateDraftReportCommentStateInput!) {
            updateAuditeeDraftReportCommentState(input: $input) {
                draftReportComment {
                    comment {
                        id,
                        content,
                        state
                    },
                    page
                }
            }
        }
    '''


CREATE_DRAFT_REPORT_REPLY = '''
        mutation createAuditeeDraftReportReply(
          $input: CreateAuditeeDraftReportReplyInput!) {
            createAuditeeDraftReportReply(input: $input) {
                draftReportReply {
                    id,
                    content
                }
            }
        }
    '''


APPROVE_AUDITEE_DRAFT_REPORT = '''
    mutation ApproveAuditeeDraftReport
      ($input: ApproveAuditeeDraftReportInput!) {
      approveAuditeeDraftReport(input: $input) {
        auditStatus {
          id
        }
      }
    }
'''

CREATE_NOTIFICATION_REVIEWED_DRAFT_REPORT = '''
        mutation createAuditeeNotificationReviewedDraftReport(
          $input: CreateNotificationReviewedDraftReportInput!) {
            createAuditeeNotificationReviewedDraftReport(input: $input) {
                draftReportComments {
                    id,
                    comment {
                        id,
                        content,
                        state
                    },
                    auditorNotified
                }
            }
        }
    '''

UPDATE_POPULATION = '''
  mutation updateAuditeePopulation(
    $input: UpdatePopulationInput!
  ) {
    updateAuditeePopulation(input: $input) {
      auditPopulation {
        id
        name
        dataFileName
        dataFile {
          name
          url
        }
        selectedSource
        configurationSaved
      }
    }
  }
'''


DELETE_POPULATION_DATA_FILE = '''
  mutation deleteAuditeePopulationDataFile(
    $input: DeletePopulationDataFileInput!
  ) {
    deleteAuditeePopulationDataFile(input: $input) {
      auditPopulation {
        id
        name
        dataFileName
        dataFile {
          name
          url
        }
      }
    }
  }
'''


ADD_COMPLETENESS_ACCURACY = '''
  mutation AddAuditeePopulationCompletenessAccuracy(
    $input: AddPopulationCompletenessAccuracyInput!
  ) {
    addAuditeePopulationCompletenessAccuracy(input: $input) {
      completenessAccuracyList {
        id
        name
        url
        populationId
      }
    }
  }
'''

UPDATE_AUDITEE_COMPLETENESS_ACCURACY = '''
  mutation UpdateAuditeePopulationCompletenessAccuracy(
    $input: UpdatePopulationCompletenessAccuracyInput!
  ) {
    updateAuditeePopulationCompletenessAccuracy(input: $input) {
      completenessAccuracy {
        id
        name
        url
        populationId
      }
    }
  }
'''

DELETE_AUDITEE_COMPLETENESS_ACCURACY = '''
  mutation DeleteAuditeePopulationCompletenessAccuracy(
    $input: DeletePopulationCompletenessAccuracyInput!
  ) {
    deleteAuditeePopulationCompletenessAccuracy(input: $input) {
      completenessAccuracy {
        id
        name
        url
        populationId
      }
    }
  }
'''

UPLOAD_POPULATION_FILE = '''
  mutation uploadAuditeePopulationFile($input: UploadPopulationFileInput!) {
    uploadAuditeePopulationFile(input: $input) {
      uploadResult {
        failedRows {
          type
          addresses
        }
        success
        auditPopulation {
          id
          name
          dataFileName
          dataFile {
            name
            url
          }
        }
      }
    }
  }
'''


CREATE_LAIKA_SOURCE_POPULATION = '''
  mutation createAuditeeLaikaSourcePopulation(
    $input: LaikaSourcePopulationInput!
    ) {
    createAuditeeLaikaSourcePopulation(input: $input) {
        laikaSourcePopulation {
            populationData {
                id
                data
            }
            errors
        }
    }
  }
'''

CREATE_LAIKA_SOURCE_COMPLETENESS_ACCURACY_FILE = '''
    mutation createAuditeeLaikaSourceCompletenessAccuracy(
        $input: LaikaSourcePopulationInput!
    ) {
        createAuditeeLaikaSourceCompletenessAccuracy(input: $input) {
            populationCompletenessAccuracy {
                id
            }
        }
    }
'''

CREATE_MANUAL_SOURCE_POPULATION = '''
  mutation createAuditeeManualSourcePopulation(
    $input: PopulationInput!
    ) {
    createAuditeeManualSourcePopulation(input: $input) {
        manualSourcePopulation {
            populationData {
                id
                data
            }
        }
    }
  }
'''


ADD_AUDITEE_AUDIT_FEEDBACK = '''
  mutation addAuditeeAuditFeedback($input: AuditFeedbackInput!) {
    addAuditeeAuditFeedback(input: $input) {
      feedback {
        id
        rate
        feedback
        reason
        user {
           id
        }
      }
    }
  }
'''
