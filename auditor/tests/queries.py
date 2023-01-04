GET_ALL_EVIDENCE = '''
        query auditorAllEvidence ($auditId: String!,
                                      $status: EvidenceStatusEnum!) {
          auditorAllEvidence (auditId: $auditId, status: $status) {
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

GET_AUDITOR_EVIDENCE_COMMENTS_BY_POOL = '''
        query Query($auditId: String!,
                    $evidenceId: String!,
                    $pool: EvidenceCommentPoolsEnum!) {
            auditorEvidenceComments(
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

GET_AUDITOR_REQUIREMENT = '''
      query requirement ($requirementId: String!, $auditId: String!) {
        requirement (requirementId: $requirementId, auditId: $auditId) {
          id
          name
          status
          description
          evidence {
            displayId
            name
            status
            attachments {
              id
              name
              file {
                url
              }
            }
          }
          criteria {
            id
            displayId
            description
          }
          test {
            id
          }
        }
      }
    '''


GET_ACCEPTED_EVIDENCE_COUNT = '''
  query auditorAcceptedEvidenceCount($auditId: String!){
      auditorAcceptedEvidenceCount(auditId: $auditId){
          acceptedEvidence
          totalEvidence
      }
  }
'''

GET_AUDITOR_EVIDENCE_DETAILS = '''
        query auditorEvidence (
          $evidenceId: String!,
          $auditId: String!,
          $isEvidenceDetail: Boolean) {
            auditorEvidence (
              evidenceId: $evidenceId,
              auditId: $auditId,
              isEvidenceDetail: $isEvidenceDetail
              ) {
                id
                displayId
                name
                status
                instructions
                description
                read
                laikaReviewed
                assignee {
                  id
                }
                tester {
                  id
                }
                requirements {
                  id
                  tester {
                    id
                  }
                }
                attachments {
                  id
                  name
                }
                samples {
                  id
                  name
                  attachments {
                    id
                    name
                    createdAt
                    file {
                      id
                      url
                    }
                  }
                }
            }
        }
    '''


GET_AUDITOR_ALL_REQUIREMENTS = '''
    query auditorAllRequirements($auditId: String!) {
        auditorAllRequirements(auditId: $auditId) {
          requirement {
            id
            displayId
            description
            evidence {
              id
              displayId
              name
            }
            tester {
              firstName
              lastName
            }
            reviewer {
              firstName
              lastName
            }
            name
          }
        }
    }
    '''

GET_REQUIREMENTS = '''
    query requirements($auditId: String!, $status: String) {
        requirements(auditId: $auditId, status: $status) {
            id
            displayId
            name
            status
          }
    }
    '''

GET_AUDITOR_CRITERIA = '''
      query auditorCriteria($auditId: String!) {
        auditorCriteria(auditId: $auditId){
          criteria {
            id
            displayId
            description
            requirements {
              id
              displayId
              name
              description
              tests {
                id
                result
              }
              evidence {
                id
                displayId
              }
            }
          }
        }
    }
    '''

GET_AUDITOR_AUDIT_EVIDENCE = '''
        query auditorAuditEvidence ($auditId: String!,
                                      $status: EvidenceStatusEnum!) {
          auditorAuditEvidence (auditId: $auditId, status: $status) {
            evidence {
                id
                name
                status
                laikaReviewed
                commentsCounter
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

GET_REQUIREMENT_COMMENT = '''
        query requirementComments (
          $requirementId: String!
          ) {
            requirementComments (
              requirementId:$requirementId
            ) {
                id
                content
                replies {
                  id
                }
            }
        }
    '''

GET_REQUIREMENT_USERS = '''
        query getRequirementAuditUsers($auditId: String!) {
            requirementAuditUsers(auditId: $auditId) {
                id
                email
            }
        }
    '''

GET_AUDITOR_ALERTS = '''
        query getAlerts($pagination: PaginationInputType) {
            auditorAlerts(pagination: $pagination) {
            newAlertsNumber
            alerts {
                id
                alertType
                senderName
                auditType
                firstName
                lastName
                requirementId
                requirementName
                commentPool
                organizationName
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

GET_AUDITOR_EVIDENCE_COMMENT_USERS = '''
        query auditorEvidenceCommentUsers
          ($auditId: String!, $pool: EvidenceCommentPoolsEnum!) {
          auditorEvidenceCommentUsers(
            auditId: $auditId
            pool: $pool
          ) {
            id
            email
          }
        }
    '''

GET_REQUIREMENT_COMMENT_USERS = '''
        query auditorRequirementCommentUsers($auditId: String!) {
                    auditorRequirementCommentUsers(auditId: $auditId) {
                        id
                        email
                    }
                }
    '''

GET_DRAFT_REPORT_FILE = '''
      query getAuditorAuditDraftReportFile($auditId: String!) {
        auditorAuditDraftReportFile(auditId: $auditId) {
          name
          content
        }
      }
  '''

GET_DRAFT_REPORT_COMMENT = '''
    query auditorDraftReportComments ($auditId: String!) {
      auditorDraftReportComments (auditId: $auditId) {
        comment {
          id
          ownerName
          state
          content
          createdAt
          replies {
              id
              ownerName
              content
              createdAt
          }
        }
        page
      }
    }
  '''

GET_DRAFT_REPORT_MENTIONS_USERS = '''
    query getAuditorDraftReportMentionsUsers($auditId: String!) {
        auditorDraftReportMentionsUsers(auditId: $auditId){
            id,
            firstName,
            role
        }
    }
    '''

GET_DRAFT_REPORT = '''
      query getDraftReport($auditId: String!) {
        auditorAuditDraftReport(auditId: $auditId) {
          name
          url
        }
      }
    '''

GET_AUDITOR_AUDIT_POPULATIONS = '''
    query auditorAuditPopulations(
      $auditId: String!
    ) {
      auditorAuditPopulations(
        auditId: $auditId
      ) {
          open {
            id
            name
            instructions
            status
            description
          }
          submitted {
            id
            name
            instructions
            status
            description
          }
        }
  }
'''

GET_AUDITOR_AUDIT_POPULATION = '''
    query auditorAuditPopulation(
        $auditId: String!,
        $populationId: String!
      ) {
      auditorAuditPopulation(
        auditId: $auditId,
        populationId: $populationId
      ) {
        id
        name
        instructions
        recommendedSampleSize
        evidenceRequest {
          id
          displayId
        }
        requirements {
          id
          displayId
        }
        populationDataCounter
      }
    }
  '''

GET_NEW_AUDITOR_EVIDENCE_REQUEST_DISPLAY_ID = '''
    query auditorNewEvidenceRequestDisplayId(
      $auditId: String!
    ) {
      auditorNewEvidenceRequestDisplayId(
        auditId: $auditId
      ) {
        displayId
      }
    }
  '''


GET_AUDITOR_POPULATION_COMMENTS = '''
        query Query($auditId: String!,
                    $populationId: String!,
                    $pool: PopulationCommentPoolsEnum!) {
            auditorPopulationComments(
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

GET_AUDITOR_COMMENT_MENTION_USERS_WITH_POOL = '''
  query auditorCommentMentionUsersWithPool
    ($auditId: String!, $pool: PopulationCommentPoolsEnum!) {
    auditorCommentMentionUsersWithPool(
      auditId: $auditId
      pool: $pool
    ) {
      id
      email
    }
  }
'''

GET_AUDITOR_ALL_CRITERIA = '''
      query auditorAllCriteria($auditId: String!) {
        auditorAllCriteria(auditId: $auditId) {
          id
          displayId
          description
          isQualified
        }
      }
    '''

AUDITOR_GET_COMPLETENESS_ACCURACY = '''
  query auditorPopulationCompletenessAccuracy(
    $auditId: String!
    $populationId: String!
  ) {
    auditorPopulationCompletenessAccuracy(
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

AUDITOR_POPULATION_DATA = '''
  query auditorPopulationData(
    $auditId: String!
    $populationId: String!
    $pagination: PaginationInputType
    $searchCriteria: String
    $isSample: Boolean
  ) {
    auditorPopulationData(
      auditId: $auditId
      populationId: $populationId
      pagination: $pagination
      searchCriteria: $searchCriteria
      isSample: $isSample
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
