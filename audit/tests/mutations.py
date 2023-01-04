CREATE_AUDIT = '''
    mutation createAudit($input: CreateAuditInput!) {
        createAudit(input: $input) {
          id
        }
    }
'''

CHECK_AUDIT_STATUS_FIELD = '''
  mutation checkAuditStatusField($input: CheckStatusFieldInput!) {
    checkAuditStatusField(input: $input) {
      id
    }
  }
'''

UPDATE_AUDIT_STAGE = '''
  mutation updateAuditStage($input: UpdateAuditStageInput!) {
    updateAuditStage(input: $input) {
      id
    }
  }
'''


AUDITOR_UPDATE_AUDIT_STAGE = '''
  mutation auditorUpdateAuditStage($input: UpdateAuditStageInput!) {
    auditorUpdateAuditStage(input: $input) {
      id
    }
  }
'''


ASSIGN_AUDIT_TO_AUDITOR = '''
    mutation assignAuditToAuditor($input: AssignAuditToAuditorInput!){
      assignAuditToAuditor(input: $input){
       auditId
      }
    }
'''

REMOVE_AUDITOR_FROM_AUDIT = '''
    mutation removeAuditorFromAudit($input: RemoveAuditorFromAuditInput!){
        removeAuditorFromAudit(input: $input){
            auditId
        }
    }
'''

DELETE_AUDITOR_USERS = '''
  mutation deleteAuditUsers($input: [String]!) {
    deleteAuditUsers(input: $input) {
      deleted
    }
  }
'''

AUDITOR_UPDATE_AUDIT_CONTENT_STEP = '''
    mutation auditorUpdateAuditContentStep($input: UpdateAuditorStepInput!) {
        auditorUpdateAuditContentStep(input: $input){
            id
        }
    }
'''

AUDITOR_UPDATE_AUDIT_DETAILS = '''
    mutation updateAuditorAuditDetails($input: UpdateAuditDetailsInput!) {
        updateAuditorAuditDetails(input: $input) {
          updated {
            id
            name
            auditConfiguration,
            auditOrganization {
              legalName
              name
              systemName
            }
        }
      }
    }
'''


UPDATE_AUDITOR = '''
    mutation updateAuditUser($input: UpdateAuditUserInput!) {
        updateAuditUser(input: $input) {
            updated
        }
    }
'''

UPDATE_AUDITOR_ROLE_IN_AUDIT_TEAM = '''
    mutation updateAuditorRoleInAuditTeam
        ($input: UpdateAuditorRoleInAuditTeamInput!) {
        updateAuditorRoleInAuditTeam(input: $input) {
            auditAuditor {
              auditor {
                user {
                  email
                }
              }
              id
              titleRole
            }
          }
        }
'''


UPDATE_AUDITOR_USER_PREFERENCES = '''
  mutation updateAuditorUserPreferences($input: UpdateAuditorUserPreferencesInput!) {
    updateAuditorUserPreferences(input: $input) {
      preferences
    }
  }
'''
