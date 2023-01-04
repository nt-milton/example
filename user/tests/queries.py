GET_USERS = '''
        query users(
            $allUsers: Boolean,
            $searchCriteria: String,
            $filter: UserFilterInputType
            $filters: [UserIncredibleFilterInputType]
        ) {
          users(
            allUsers: $allUsers,
            searchCriteria: $searchCriteria,
            filter: $filter,
            filters: $filters
          ) {
            data {
              id
              email
              firstName
              lastName
              lastActivityDate
              permissions
              role
              status
              userPreferences
              securityTraining
            }
            permissions
            success
          }
        }
    '''


GET_USERS_ORG_INPUT = '''
        query users(
            $allUsers: Boolean,
            $searchCriteria: String,
            $filter: UserFilterInputType
            $filters: [UserIncredibleFilterInputType]
            $organizationId: String
        ) {
          users(
            allUsers: $allUsers,
            searchCriteria: $searchCriteria,
            filter: $filter,
            filters: $filters,
            organizationId: $organizationId
          ) {
            data {
              id
              email
              firstName
              lastName
              lastActivityDate
              permissions
              role
              status
              userPreferences
              securityTraining
            }
            permissions
            success
          }
        }
    '''

GET_USER = '''
        query user(
            $id: String
        ) {
          user(
            id: $id
          ) {
            data {
              id
              email
              firstName
              lastName
              lastActivityDate
              permissions
              role
              status
              userPreferences
              securityTraining
            }
            success
          }
        }
    '''

GET_USERS_WITH_LO_IDS = '''
        query users(
            $allUsers: Boolean,
            $searchCriteria: String,
            $filter: UserFilterInputType
            $filters: [UserIncredibleFilterInputType]
        ) {
          users(
            allUsers: $allUsers,
            searchCriteria: $searchCriteria,
            filter: $filter,
            filters: $filters
          ) {
            data {
              id
              email
              firstName
              lastName
              lastActivityDate
              permissions
              role
              status
              userPreferences
              loUserIds
            }
            permissions
            success
          }
        }
    '''

GET_USERS_WITH_COMPLIANT = '''
        query users(
            $allUsers: Boolean,
            $searchCriteria: String,
            $filter: UserFilterInputType
            $filters: [UserIncredibleFilterInputType]
        ) {
          users(
            allUsers: $allUsers,
            searchCriteria: $searchCriteria,
            filter: $filter,
            filters: $filters
          ) {
            data {
              id
              email
              firstName
              lastName
              lastActivityDate
              permissions
              role
              status
              userPreferences
              compliantCompleted
            }
            permissions
            success
          }
        }
    '''

GET_USERS_BY_ROLE = '''
        query usersByRole(
            $allUsers: Boolean,
            $searchCriteria: String,
            $filter: UserFilterInputType
        ) {
          usersByRole(
            allUsers: $allUsers,
            searchCriteria: $searchCriteria,
            filter: $filter
          ) {
            data {
              id
              email
              firstName
              lastName
              lastActivityDate
              permissions
              role
              status
              userPreferences
            }
            permissions
            success
          }
        }
    '''

GET_DISCOVERED_PEOPLE = '''
        query {
          discoveredPeople{
            data {
              id
              email
              firstName
              lastName
              lastActivityDate
              permissions
              role
              status
              userPreferences
              discoveryState
            }
          }
        }
    '''

UPDATE_USER = '''
        mutation updateUser($input: UserInput!) {
            updateUser(input: $input) {
                success
                data {
                    userPreferences
                }
                error {
                    code
                    message
                }
            }
        }
    '''

UPDATE_USER_EMAIL = '''
        mutation updateUserEmail($input: UserInputEmail!) {
            updateUserEmail(input: $input) {
                success
                data {
                    userPreferences
                }
                error {
                    code
                    message
                }
            }
        }
    '''

UPDATE_USER_PREFERENCES = '''
        mutation updateUserPreferences($input: UserInput!) {
            updateUserPreferences(input: $input) {
                data {
                    email
                    userPreferences
                }
            }
        }
    '''

DELETE_USERS = '''
  mutation deleteUsers($input: [String]!) {
    deleteUsers(input: $input) {
      deleted
    }
  }
'''

GET_CSM_AND_CA_USERS = '''
  query getCSMAndCAUsers {
    csmAndCaUsers {
        users {
            id
            firstName
            lastName
        }
    }
  }
'''


GET_AUDITORS = '''
  query getAuditors {
    allAuditors {
        users {
            id
            firstName
            lastName
        }
    }
  }
'''

INVITE_USER_TO_ORGANIZATION = '''
mutation inviteUser($input: InviteToOrganizationInput!) {
    inviteToOrganization(input: $input) {
        success
        data {
        ...laikaUserDetails
        __typename
        }
        error {
        code
        message
        __typename
        }
        __typename
    }
}

fragment laikaUserDetails on UserType {
  id
  email
  firstName
  lastName
  lastActivityDate
  permissions
  role
  status
  title
  manager {
      id
      firstName
      lastName
      email
      __typename
  }
  department
  employmentType
  employmentSubtype
  startDate
  endDate
  employmentStatus
  phoneNumber
  userPreferences
  isActive
  __typename
}
'''

RESEND_INVITATION = '''
  mutation ResendInvitation($email: String!) {
    resendInvitation(email: $email) {
      success
    }
  }
'''

GET_CONCIERGE_PARTNERS = '''
  query conciergePartners {
    conciergePartners {
      id
      name
    }
  }
'''

BULK_INVITE_USER = '''
    mutation BulkInviteUser($input: BulkInviteUserInput!) {
        bulkInviteUser(input: $input) {
            uploadResult {
                ...uploadResultDetails
                __typename
            }
            invitedUsers {
                ...laikaUserDetails
                __typename
            }
            __typename
        }
    }

fragment laikaUserDetails on UserType {
  id
  email
  firstName
  lastName
  lastActivityDate
  permissions
  role
  status
  title
  manager {
    id
    firstName
    lastName
    email
    __typename
  }
  department
  employmentType
  employmentSubtype
  startDate
  endDate
  employmentStatus
  backgroundCheckStatus
  backgroundCheckPassedOn
  phoneNumber
  userPreferences
  isActive
  compliantCompleted
  securityTraining
  policiesReviewed
  offboarding {
    id
    document {
      id
      url
      __typename
    }
    __typename
  }
  policiesReviewedData {
    id
    name
    metadata
    status
    dueDate
    __typename
  }
  __typename
}

fragment uploadResultDetails on UploadResultType {
  title
  iconName
  iconColor
  successfulRows
  failedRows
  invalidCells {
    requiredFields
    invalidCategory
    invalidMultiChoice
    __typename
  }
  message
  __typename
}
'''

DELEGATE_USER_INTEGRATION = '''
mutation delegateUserIntegration($input: DelegateUserIntegrationInput!) {
  delegateUserIntegration(input: $input) {
    email
  }
}
'''

DELEGATE_UNINVITED_USER_INTEGRATION = '''
mutation delegateUninvitedUserIntegration(
    $input: DelegateUninvitedUserIntegrationInput!
) {
  delegateUninvitedUserIntegration(input: $input) {
    email
  }
}
'''
