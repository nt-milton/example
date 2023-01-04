GET_CERTIFICATION_LIST = '''
        query CertificationList {
            certificationList {
                id
                name
            }
        }
    '''


GET_CERTIFICATION_LIST_BY_ORG = '''
        query CertificationsByOrganization($id: UUID!) {
            certificationsByOrganization(id: $id) {
                data {
                    certification {
                        id
                    }
                }
                error {
                    code
                    message
                }
                success
            }
        }
    '''

GET_MY_COMPLIANCE_CERTIFICATIONS = '''
        query Certifications {
            complianceCertificationList {
                id
                name
            }
        }
    '''

GET_ALL_CERTIFICATION_LIST_BY_ORG = '''
        query AllCertificationsByOrganization {
            allCertificationsByOrganization {
                data {
                    certification {
                        id
                    }
                }
                error {
                    code
                    message
                }
                success
            }
        }
    '''

UPDATE_UNLOCK_ORGANIZATION = '''
        mutation UpdateUnlockCertification(
            $input: UnlockedOrganizationCertificationInput!
        ) {
            updateUnlockCertification(input: $input) {
                success
                error {
                    code
                    message
                }
            }
        }
    '''

GET_ALL_CERTIFICATES = '''
    query getAllCertificationList {
        allCertificationList {
            id
            name
            progress
            isLocked
            logoFile {
                id
                url
            }
        }
    }
'''

GET_SEED_PROFILES = '''
   query getSeedProfiles {
        seedProfiles {
          id
          name
          contentDescription
          createdAt
          file
          defaultBase
        }
  }
'''

GET_CERTIFICATIONS_FOR_PLAYBOOKS_MIGRATION = '''
        query getCertificationsForPlaybooksMigration {
            certificationsForPlaybooksMigration {
                id
                name
            }
        }
    '''

GET_UNLOCKED_CERTIFICATION_PROGRESS_PER_USER = '''
    query getUnlockedCertificationProgressPerUser($id: ID!) {
        unlockedCertificationProgressPerUser(id: $id) {
            id
            progress
            userId
        }
    }
'''
