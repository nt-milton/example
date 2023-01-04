UPDATE_AUDIT_DATES_UNLOCKED_CERTIFICATION = '''
    mutation updateAuditDatesUnlockedOrgCertification
            ($input: UnlockedOrganizationCertificationAuditDatesInput!) {
                updateAuditDatesUnlockedOrgCertification(input: $input) {
                  unlockedOrgCertification {
                    id
                    targetAuditStartDate
                    targetAuditCompletionDate
                  }
            }
    }
'''

UPDATE_AUDIT_COMPLETION_DATE = '''
    mutation updateAuditCompletionDate
            ($input: UnlockedCertificationCompletionDateInput!) {
                updateAuditCompletionDate(input: $input) {
                  unlockedOrgCertification {
                    id
                    targetAuditCompletionDate
                  }
            }
    }
'''
