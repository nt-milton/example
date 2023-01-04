GET_DASHBOARD_ITEMS = '''
        query getActionItems(
            $orderBy: OrderInputType
            $filter: JSONString
            $actionItemsStatus: String
            $pagination: PaginationInputType!
        ) {
            actionItems(
              orderBy: $orderBy
              filter: $filter
              actionItemsStatus: $actionItemsStatus
              pagination: $pagination
            ) {
                data {
                    id
                    uniqueActionItemId
                    startDate
                    dueDate
                    type
                    description
                    referenceUrl
                    isRequired
                    isRecurrent
                    seen
                    status
                    group
                    completedOn
                    subtaskText
                }
            }
        }
    '''

GET_TASK_VIEW_ITEMS = '''
        query getTaskViewActionItemsActionItems(
            $filter: JSONString
            $actionItemsStatus: String
        ) {
            taskViewActionItems(
              filter: $filter
              actionItemsStatus: $actionItemsStatus
            ) {
                data {
                    id
                    uniqueActionItemId
                    startDate
                    dueDate
                    type
                    description
                    referenceUrl
                    isRequired
                    isRecurrent
                    seen
                    status
                    group
                    completedOn
                    subtaskText
                }
            }
        }
    '''

GET_QUICK_LINKS = '''
  query getQuickLinks {
    quickLinks {
        id
        name
        total
        dataNumber
      }
    }
'''

GET_FRAMEWORK_CARDS = '''
  query getFrameworkCards {
    frameworkCards {
      id
      frameworkName
      controls
      operational
      needsAttention
      notImplemented
      progress
      logoUrl
    }
  }
'''
