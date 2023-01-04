GET_CONTROL_GROUPS = '''
  query getGroups($organizationId: String!,
  $searchCriteria: String,
  $filteredUnlockedFramework: String) {
    groups(organizationId: $organizationId,
    searchCriteria: $searchCriteria,
    filteredUnlockedFramework: $filteredUnlockedFramework)
    {
      id
      name
      dueDate
      referenceId
      sortOrder
      controls {
        id
        key: id
        name
        displayId
        index: displayId
        referenceId
        pillar {
          id
          name
          description
        }
        allCertifications {
          id
          displayName
        }
      }
    }
  }
'''

GET_BACKLOG_CONTROLS = '''
  query getBacklog($organizationId: String!, $searchCriteria: String) {
    backlog(organizationId: $organizationId, searchCriteria: $searchCriteria) {
      id
      key: id
      name
      displayId
      index: displayId
      referenceId
      pillar {
        id
        name
        description
      }
      allCertifications {
        id
        displayName
      }
    }
  }
'''

GET_ALL_GROUPS = '''
  query getAllGroups($organizationId: String!) {
    allGroups(organizationId: $organizationId) {
      id
      key: id
      name
      dueDate
      referenceId
      sortOrder
    }
  }
'''
