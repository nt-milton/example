GET_ARCHIVED_PROGRAMS_QUERY = '''
        query getArchivedPrograms {
            archivedPrograms {
              id,
              data
        }
      }
    '''

GET_ARCHIVED_PROGRAM_QUERY = '''
        query getArchivedProgram($id: UUID!) {
            archivedProgram(id: $id) {
              id,
              data
        }
      }
    '''

GET_ARCHIVED_TASKS_QUERY = '''
        query getArchivedTasks($id: UUID!) {
            archivedTasks(id: $id) {
                id
                data
                subtasks {
                    id
                    data
                }
                evidence {
                    id
                    name
                    type
                    description
                }
            }
        }
    '''

GET_PROGRAMS_QUERY = '''
        query getPrograms {
            programs{
              id,
              sortIndex,
              name,
              description,
              isLocked,
              programLead {
                id,
                email,
                firstName,
                lastName,
              }
              progress,
              certifications {id, name, logoFile{id, url}, isLocked, progress}
              allCertificatesCount
        }
      }
    '''

GET_TASK_DETAILS_QUERY = '''
        query taskDetails($id: UUID!) {
            task(id: $id) {
                id
                name
                description
                category
                overview
                implementationNotes
                programId
                tier
                progress
                badges
                customerNumber
                subtasks {
                    id
                    name
                    subtasks {
                        text
                    }
                }
            }
        }
    '''

GET_SUBTASK_QUERY = '''
        query getSubtask($id: UUID!) {
            subtask(id: $id) {
                id
                text
                group
                assignee {
                  email
                  firstName
                  id
                  lastName
                }
                requiresEvidence
                certifications
                sortIndex
                badges
                dueDate
                status
                priority
                customerNumber
                task
                evidence {
                  id
                  name
                  link
                  type
                  date
                }
            }
        }
    '''

GET_TASK_SUBTASK_QUERY = '''
        query taskSubtasks($id: UUID!) {
            task(id: $id) {
                id
                name
                category
                programId
                tier
                progress
                implementationNotes
                subtasks {
                    id
                    name
                    subtasks {
                        id
                        text
                        group
                        requiresEvidence
                        sortIndex
                        badges
                        dueDate
                        status
                        priority
                        customerNumber
                        evidence {
                            id
                            name
                            link
                            type
                            date
                            systemTagCreatedAt
                        }
                    }
                }
                updatedAt
            }
        }
    '''

GET_PROGRAM_DETAILS_QUERY = '''
        query getProgram($id: UUID!) {
            program(id: $id) {
                program {
                    id
                    description
                    progress,
                    name
                }
                tasks {
                    id
                    name
                    tasks {
                        id
                        name
                        description
                    }
                }
            }
        }
    '''

GET_TASK_COMMENTS = '''
        query taskComments($id: UUID!) {
            task(id: $id) {
                comments {
                  id
                  owner {
                    id
                    firstName,
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
                      firstName,
                      lastName
                    }
                    ownerName
                    content
                    createdAt
                    updatedAt
                  }
                }
            }
        }
    '''

GET_PROGRAM_DETAIL_QUERY = '''
        query getProgramDetail($id: UUID!) {
            programDetail(id: $id) {
                id
                progress
                name
                programLead {
                    id
                    email
                    firstName
                    lastName
                }
            }
        }
    '''

GET_PROGRAM_CERTIFICATES = '''
        query getProgramCertificates($id: UUID!) {
            programCertificates(id: $id) {
                certificates {
                    id
                    name
                    logoFile {
                      id
                      url
                    }
                    progress
                    isLocked
                }
            }
        }
    '''

GET_PROGRAM_ALL_CERTIFICATES = '''
        query getProgramAllCertificates($id: UUID!) {
            programCertificates(id: $id) {
                allCertificates {
                    id
                    name
                    logoFile {
                      id
                      url
                    }
                    progress
                    isLocked
                }
            }
        }
    '''

GET_PROGRAM_TASKS = '''
        query getProgramTasks($id: UUID!) {
            programTasks(id: $id) {
                tasks {
                    id
                    name
                    tasks {
                      id
                      name
                      category
                      customerNumber
                      unlockedCertificates
                    }
                }
            }
        }
    '''

GET_ALERTS_QUERY = '''
    query getAlerts($pagination: PaginationInputType) {
      alerts(pagination: $pagination) {
        data {
            id
            senderName
            action
            receiverName
            url
            createdAt
            commentId
            subtaskGroup
            commentState
            taskName
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

GET_HAS_NEW_ALERTS = '''
        query getAlerts {
            hasNewAlerts
        }
    '''

GET_ORGANIZATION_PROGRAMS = '''
        query getOrganizationPrograms(
            $id: UUID!
        ) {
            organizationPrograms(
            id: $id
            ) {
            id
            name
            }
        }
    '''
