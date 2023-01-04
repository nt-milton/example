CREATE_ORGANIZATION_VENDOR_MUTATION = '''
    mutation createOrganizationVendor($input: CreateOrganizationVendorInput!) {
      createOrganizationVendor(input: $input) {
        success
        __typename
      }
    }
    '''

GET_ORGANIZATION_VENDOR = '''
    query getOrganizationVendor($id: Int!) {
      organizationVendor(id: $id) {
        id
        status
        riskRating
        riskAssessmentDate
        financialExposure
        operationalExposure
        dataExposure
        purposeOfTheSolution
        additionalNotes
        contractRenewalDate
        contractStartDate
        primaryExternalStakeholderName
        primaryExternalStakeholderEmail
        secondaryExternalStakeholderName
        secondaryExternalStakeholderEmail
        internalStakeholders {
          id
          username
          firstName
          lastName
          email
          role
          __typename
        }
        documents {
          id
          name
          description
          link
          evidenceType
          date
          linkable
          contentId
          __typename
        }
        vendor {
          id
          name
          website
          description
          isPublic
          logo {
            name
            url
            __typename
          }
          certifications {
            id
            name
            url
            logo {
              name
              url
              __typename
            }
            __typename
          }
          categories {
            id
            name
            __typename
          }
          __typename
        }
        vendorUsers {
          name
          email
          createdAt
          userData {
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
            employmentStatus
            employmentType
            employmentSubtype
            department
            phoneNumber
            startDate
            endDate
            backgroundCheckPassedOn
            backgroundCheckStatus
            title
            manager {
              id
              firstName
              lastName
              username
              __typename
            }
            offboarding {
              id
              document {
                id
                url
                __typename
              }
              __typename
            }
            __typename
          }
          __typename
        }
        __typename
      }
    }
    '''

UPDATE_ORGANIZATION_VENDOR_MUTATION = '''
    mutation updateOrganizationVendor(
        $id: Int!, $input: UpdateOrganizationVendorInput!
    ) {
      updateOrganizationVendor(id: $id, input: $input) {
        success
        __typename
      }
    }
'''


VENDOR_CANDIDATES_QUERY = '''
    query {
        vendorCandidates {
            new {
                id
                name
            }
            ignored {
                id
                name
            }
        }
    }
    '''


CONFIRM_VENDOR_CANDIDATE_MUTATION = '''
    mutation($confirmedVendorIds: [ID!], $ignoredVendorIds: [ID!]) {
        confirmVendorCandidates(
            confirmedVendorIds: $confirmedVendorIds,
            ignoredVendorIds: $ignoredVendorIds
        ) {
            vendorIds
        }
    }
    '''


DELETE_ORGANIZATION_VENDOR_MUTATION = '''
    mutation deleteOrganizationVendor($input: DeleteOrganizationVendorInput!) {
      deleteOrganizationVendor(input: $input) {
        success
        __typename
      }
    }
    '''


VENDOR_FILTERS = '''
    query {
        filteredOrganizationVendors {
            filters {
                id
                category
                items {
                    id
                    name
                }
            }
        }
    }
    '''


GET_FILTERED_VENDORS_WITH_ORDER_BY = '''
    query getFilteredOrganizationVendors(
      $orderBy: VendorOrderInputType
    ) {
      filteredOrganizationVendors(
        orderBy: $orderBy
      ) {
        data {
          id
          status
          riskRating
          riskRatingRank
        }
      }
    }
    '''


GET_ORGANIZATION_VENDORS_FOR_ACCESS_REVIEW = '''
    query serviceAccountsPerVendor(
        $id: ID!,
        $searchCriteria: String,
        $pagination: PaginationInputType,
        $orderBy: [OrderInputType]
    ) {
        serviceAccountsPerVendor(
            id: $id,
            searchCriteria: $searchCriteria,
            pagination: $pagination,
            orderBy: $orderBy
        ) {
            results {
                id
                username
                connection
                email
                groups
            }
        }
    }
'''
