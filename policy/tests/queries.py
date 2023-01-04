GET_PUBLISHED_POLICIES = '''
  query getPublishedPolicies($dataroomOnly: Boolean) {
    publishedPolicies(dataroomOnly: $dataroomOnly) {
      data {
        description
        displayId
        id
        isPublished
        name
        updatedAt
      }
    }
  }
'''


GET_POLICIES_QUERY = '''
  query getPolicies($orderBy: PolicyOrderInputType) {
      policies(orderBy: $orderBy) {
          success
          data {
              category
              id
              displayId
              isPublished
              name
              permissions
              updatedAt
              ownerDetails {
                id
                firstName
                lastName
                email
              }
              owner {
                ...user
              }
          }
          error {
              code
              message
          }
          permissions
          __typename
      }
  }
'''

GET_FILTERED_POLICIES = '''
query getFilteredPolicies(
    $pageSize: Int,
    $page: Int,
    $filters: FiltersPolicyType,
    $orderBy: PolicyOrderInputType) {
  filteredPolicies(
    pageSize: $pageSize
    page: $page
    filters: $filters
    orderBy: $orderBy
  ) {
    success
    data {
      category
      id
      displayId
      isPublished
      isVisibleInDataroom
      name
      permissions
      updatedAt
      ownerDetails {
        id
        firstName
        lastName
        email
      }
      owner {
        ...user
      }
      tags
      controlFamily {
        id
        name
        description
      }
      policyType

    }
    pagination {
      page
      current
      total
      pages
      hasNext
      hasPrev
    }
    error {
      code
      message
    }
    permissions
  }
}

fragment user on UserType {
  id
  email
  firstName
  username
  lastName
}
'''

GET_POLICY_FILTERS = '''
query getPolicyFilters {
  policyFilters {
    id
    category
    items {
      id
      name
    }
  }
}
'''

GET_POLICY_CONTROLS = '''
    query getPolicy($id: UUID!) {
        policy(id: $id) {
          success
          data {
            id
            controls {
              id
            }
        }
      }
    }
'''
