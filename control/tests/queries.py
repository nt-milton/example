GET_CONTROL_DETAILS = '''
  query getControlDetails($id: UUID!) {
    control(id: $id) {
      id
      status
      health
      flaggedMonitors
      allActionItemsHaveNoAssignees
      comments {
        id
        owner {
          id
          firstName
          lastName
        }
        ownerName
        content
        createdAt
        updatedAt
        replies {
          id
          owner {
            id
            firstName
            lastName
          }
          ownerName
          content
          createdAt
          updatedAt
        }
        state
        isDeleted
      }
    }
  }
'''

GET_CONTROL_EVIDENCES = '''
  query getControlEvidences(
    $id: UUID!
    $pagination: PaginationInputType
  ) {
    controlEvidence(id: $id, pagination: $pagination) {
      data {
        id
        name
        description
        link
        type: evidenceType
        date
        linkable
        contentId
      }
      pagination {
        current
        pageSize
        total
      }
    }
  }
'''

GET_CONTROLS_FILTERS = '''
  query getControlsFilters{
    controlsFilters{
      data {
        category
        items {
          id
          name
        }
      }
    }
  }
'''

GET_CONTROL_ACTION_ITEMS = '''
  query getControlActionItems($id: UUID!) {
    controlActionItems (id: $id) {
      id
      name
      description
      completionDate
      dueDate
      isRequired
      isRecurrent
      recurrentSchedule
      status
      metadata
      evidenceMetadata {
        referenceId
        name
        description
        attachment {
          name
          url
        }
    }
      owner {
        id
        email
      }
      controls {
        id
        referenceId
      }
      evidences {
        id
      }
      trayData {
        typeKey
        descriptionKey
        labelKey
      }
    }
  }
'''

GET_CONTROLS_PER_FAMILY = '''
   query getControlsPerFamily {
       controlsPerFamily {
          id
          familyName
          familyControls {
              id
              referenceId
              name
              description
              ownerDetails {
                  id
                  firstName
                  lastName
                  email
              }
           }
       }
   }
'''

CONTROL_BANNER_COUNTER = '''
  query getControlBannerCounter($filters: RoadmapFilterInputType) {
    controlBannerCounter(filters: $filters) {
      totalControls
      assignedControls
    }
  }
'''

GET_MIGRATION_HISTORY = '''
    query getMigrationHistory($id: UUID!) {
        migrationHistory(id: $id) {
            createdAt
            createdBy {
                id
                firstName
                lastName
                email
            }
            frameworksDetail
            status
            mappedSubtasks
        }
    }
'''
