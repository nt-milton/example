GET_AUDITS_IN_PROGRESS = '''
      query getAuditsInProgress {
        auditsInProgress {
          id
          name
          auditType {
            id
            type
            framework {
              id
              description
              type
              logo {
                id
                url
              }
            }
          }
          status {
            id
            currentStatus
          }
        }
      }
    '''
GET_PAST_AUDITS = '''
      query getPastAudits {
        pastAudits {
          id
          name
          auditType {
            id
            type
          }
          auditFirm
          completedAt
        }
      }
    '''

GET_AUDITOR_PAST_AUDITS = '''
      query getAuditorPastAudits($pagination: PaginationInputType,
      $orderBy: OrderInputType, $searchCriteria: String) {
        auditorPastAudits(
          pagination: $pagination,
          orderBy: $orderBy,
          searchCriteria: $searchCriteria
        ) {
          audits {
            id
            name
            status {
              currentStatus
            }
            auditType {
              type
            }
            organization
            completedAt
            auditorList {
              user {
                firstName
                lastName
              }
            }
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

GET_AUDIT_TYPES = '''
      query getAuditTypes {
        auditTypes {
          id,
          type,
          framework {
            id
            description
            type
            logo {
              id
              url
            }
          }
          auditFirm {
            name
          },
          coupons
        }
      }
    '''

GET_AUDIT = '''
      query getAudit($id: String!) {
        audit(id: $id) {
          id
          auditType {
            type
            feedbackReasons
          }
          status {
            draftReportApproved
            draftReportApprovedTimestamp
            draftReportApproverName
            representationLetterLinkStatus
            managementAssertionLinkStatus
            subsequentEventsQuestionnaireLinkStatus
            engagementLetterLinkStatus
            controlDesignAssessmentLinkStatus
          }
          feedback {
              rate
              feedback
          }
        }
      }
    '''

GET_AUDITOR_AUDIT = '''
      query getAudit($id: String!) {
        auditorAudit(id: $id) {
          id
          draftReportSections {
            name
            url
            section
            fileName
          }
        }
      }
    '''

# Auditor queries

GET_AUDITOR_ONGOING_AUDITS = '''
      query getAuditorOngoingAudits($pagination: PaginationInputType,
      $orderBy: OrderInputType, $searchCriteria: String) {
        auditorOngoingAudits(
          pagination: $pagination,
          orderBy: $orderBy,
          searchCriteria: $searchCriteria
        ) {
          audits {
            id
            completedAt
            createdAt
            name
            organization
            auditType {
              type
            }
            auditorList {
              user {
                firstName
                lastName
              }
            }
            status {
              currentStatus
            }
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

GET_ALL_ONGOING_AUDITS = '''
    query getAllOngoingAudits($pagination: PaginationInputType,
    $orderBy: OrderInputType, $searchCriteria: String) {
      allOngoingAudits(
        pagination: $pagination,
        orderBy: $orderBy,
        searchCriteria: $searchCriteria
      ) {
        audits {
          id
          name
          createdAt
          organization
          auditType {
            type
          }
          auditorList {
            user {
              firstName
              lastName
            }
          }
          status {
            currentStatus
          }
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

GET_AUDIT_TEAM = '''
    query getAuditAuditorTeam($id: String!) {
        auditTeam(id: $id) {
            auditors{
              id
              user{
                id
                email
              }
              auditInProgress
              role
            }
        }
    }
 '''

GET_AUDITORS = '''
    query getAuditors($pagination: PaginationInputType) {
      auditors(pagination: $pagination) {
        auditors {
          user{
            ...laikaUserDetails
          }
          auditInProgress
        }
        pagination{
          current
          pageSize
          total
          hasNext
        }
      }
    }
    fragment laikaUserDetails on UserType {
      id
      email
      firstName
      lastName
      lastActivityDate
      role
    }
 '''

GET_AUDITOR_USERS = '''
    query getAuditorUsers {
        auditorUsers {
          user {
            id
            email
            firstName
            lastName
          }
        }
    }
 '''

GET_AUDITOR_USER = '''
  query {
    auditorUser {
      data {
        id
        email
        firstName
        lastName
      }
      auditFirm
    }
  }
 '''

GET_AUDITOR_DRAFT_REPORT_SECTION_CONTENT = '''
    query getAuditorDraftReportSectionContent($auditId: String!, $section: String!){
        auditorDraftReportSectionContent(auditId: $auditId, section: $section){
          id
          sectionContent
        }
    }
'''
