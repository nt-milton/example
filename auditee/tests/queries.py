GET_ALL_EVIDENCE = '''
        query auditeeAllEvidence ($auditId: String!,
                                   $status: EvidenceStatusEnum!) {
          auditeeAllEvidence (auditId: $auditId, status: $status) {
              evidence {
                id
                name
                status
                laikaReviewed
                assignee {
                  firstName
                  lastName
                }
                requirements {
                  id
                  name
                }
                attachments {
                  id
                  name
                  description
                  createdAt
                }
              }
          __typename
          }
        }
    '''

GET_AUDITEE_ACCEPTED_EVIDENCE_COUNT = '''
  query auditeeAcceptedEvidenceCount($auditId: String!){
      auditeeAcceptedEvidenceCount(auditId: $auditId){
          acceptedEvidence
          totalEvidence
      }
  }
'''

GET_AUDITEE_REVIEWED_EVIDENCE_COUNT = '''
  query auditeeReviewedEvidenceCount ($auditId: String!) {
    auditeeReviewedEvidenceCount(auditId: $auditId) {
      laikaReviewedEvidence
      totalEvidence
    }
  }
'''

GET_AUDITEE_EVIDENCE = '''
        query auditeeEvidence (
            $evidenceId: String!,
            $auditId: String!,
            $isEvidenceDetail: Boolean
        ) {
          auditeeEvidence (
            evidenceId: $evidenceId,
            auditId: $auditId,
            isEvidenceDetail: $isEvidenceDetail
        ) {
            id
            name
            attachments {
                id
                name
            }
            displayId
            samples {
                id
                name
                attachments {
                    id
                    name
                }
            }
          }
        }
    '''

GET_AUDITEE_EVIDENCE_ASSIGNEES = '''
  query auditeeAssigneesForEvidence($auditId: String!) {
    auditeeAssigneesForEvidence(auditId: $auditId) {
      id
      firstName
      lastName
      email
    }
  }
'''

GET_AUDITEE_EVIDENCE_COMMENT_USERS = '''
  query auditeeEvidenceCommentUsers
    ($auditId: String!, $pool: EvidenceCommentPoolsEnum!) {
    auditeeEvidenceCommentUsers(
      auditId: $auditId
      pool: $pool
    ) {
      id
      email
    }
  }
'''

GET_AUDITEE_DOCUMENTS = '''
  query auditeeDocuments
    ($auditId: String!) {
    auditeeDocuments(
      auditId: $auditId
    ) {
      documents {
      id
      name
      type
      createdAt
      updatedAt
      extension
      tags {
        id
        name
        type
      }
      description
      file {
        url
      }
    }
    categories
    haveAuditType
    }
  }
'''

GET_FIELDWORK_AUDITEE_EVIDENCE = '''
        query auditeeEvidenceList ($auditId: String!,
                                   $status: EvidenceStatusEnum!) {
          auditeeEvidenceList (auditId: $auditId, status: $status) {
              evidence {
                id
                name
                status
                laikaReviewed
                assignee {
                  firstName
                  lastName
                }
                requirements {
                  id
                  name
                }
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

GET_AUDITEE_EVIDENCE_COMMENTS_BY_POOL = '''
        query Query($auditId: String!,
                    $evidenceId: String!,
                    $pool: EvidenceCommentPoolsEnum!) {
            auditeeEvidenceComments(
                auditId: $auditId,
                evidenceId: $evidenceId,
                pool: $pool) {
                    id
                    owner {
                        email
                    }
                    ownerName
                    content
                    createdAt
                    isInternalComment
                    replies {
                        id
                        owner {
                            email
                        }
                        ownerName
                        content
                        createdAt
                    }
            }
        }
    '''

GET_AUDITEE_ALERTS = '''
        query getAlerts($pagination: PaginationInputType) {
            alerts(pagination: $pagination) {
                data {
                    id
                    senderName
                    receiverName
                    url
                    type
                    commentPool
                    auditName
                    auditType
                }
                pagination {
                    current
                    pageSize
                    total
                    hasNext
                }
            }
        }
    '''

GET_DRAFT_REPORT_COMMENTS = '''
    query getAuditeeDraftReportComments($auditId: String!) {
        auditeeDraftReportComments(auditId: $auditId){
            id,
            comment {
                id,
                content
            },
            page
        }
    }
    '''

GET_DRAFT_REPORT_MENTIONS_USERS = '''
    query getAuditeeDraftReportMentionsUsers($auditId: String!) {
        auditeeDraftReportMentionsUsers(auditId: $auditId){
            id,
            firstName,
            role
        }
    }
    '''

GET_DRAFT_REPORT = '''
      query getDraftReport($auditId: String!) {
        auditeeAuditDraftReport(auditId: $auditId) {
          name
          url
        }
      }
    '''

GET_AUDITEE_AUDIT_POPULATION = '''
    query auditeeAuditPopulation(
        $auditId: String!,
        $populationId: String!
      ) {
      auditeeAuditPopulation(
        auditId: $auditId,
        populationId: $populationId
      ) {
        id
        name
        instructions
        evidenceRequest {
          id
          displayId
        }
        requirements {
          id
          displayId
        }
        populationDataCounter
        columnTypes
      }
    }
  '''


GET_AUDITEE_AUDIT_POPULATIONS = '''
    query auditeeAuditPopulations(
      $auditId: String!
    ) {
      auditeeAuditPopulations(
        auditId: $auditId
      ) {
          open {
            id
            name
            instructions
            status
            description
            commentsCounter
          }
          submitted {
            id
            name
            instructions
            status
            description
            commentsCounter
          }
        }
    }
  '''


GET_AUDITEE_POPULATION_COMMENTS_BY_POOL = '''
        query Query($auditId: String!,
                    $populationId: String!,
                    $pool: PopulationCommentPoolsEnum!) {
            auditeePopulationComments(
                auditId: $auditId,
                populationId: $populationId,
                pool: $pool) {
                    id
                    owner {
                        email
                    }
                    ownerName
                    content
                    createdAt
                    replies {
                        id
                        owner {
                            email
                        }
                        ownerName
                        content
                        createdAt
                    }
            }
        }
    '''


GET_AUDITEE_POPULATION_COMMENT_USERS = '''
  query auditeePopulationCommentUsers
    ($auditId: String!, $pool: PopulationCommentPoolsEnum!) {
    auditeePopulationCommentUsers(
      auditId: $auditId
      pool: $pool
    ) {
      id
      email
    }
  }
'''

GET_AUDITEE_AUDIT_POPULATION_CONFIGURATION = '''
        query auditeeAuditPopulation(
            $auditId: String!,
            $populationId: String!
        ) {
            auditeeAuditPopulation(
                auditId: $auditId,
                populationId: $populationId
            ) {
                configurationSeed
            }
        }
    '''

AUDITEE_GET_COMPLETENESS_ACCURACY = '''
  query auditeePopulationCompletenessAccuracy(
    $auditId: String!
    $populationId: String!
  ) {
    auditeePopulationCompletenessAccuracy(
      populationId: $populationId
      auditId: $auditId
    ) {
      id
      name
      url
      populationId
    }
  }
'''

AUDITEE_POPULATION_DATA = '''
  query auditeePopulationData(
    $auditId: String!
    $populationId: String!
    $pagination: PaginationInputType
  ) {
    auditeePopulationData(
      auditId: $auditId
      populationId: $populationId
      pagination: $pagination
    ) {
      populationData {
        id
        data
      }
      pagination {
        page,
        pages,
        pageSize,
      }
    }
  }
'''


AUDITEE_POPULATION_CONFIGURATION_QUESTIONS = '''
query auditeePopulationConfigurationQuestions(
  $auditId: String!
  $populationId: String!
) {
  auditeePopulationConfigurationQuestions(
    auditId: $auditId
    populationId: $populationId
  ) {
    id
    question
    answers
    type
    column
    operator
  }
}
'''


AUDITEE_POPULATION_LAIKA_SOURCE_DATA_EXISTS = '''
        query auditeeAuditPopulation(
            $auditId: String!,
            $populationId: String!
        ) {
            auditeeAuditPopulation(
                auditId: $auditId,
                populationId: $populationId
            ) {
                laikaSourceDataDetected
            }
        }
    '''
