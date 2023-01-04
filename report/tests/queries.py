GET_REPORTS = '''
        query reports(
            $orderBy: OrderInputType,
            $pagination: PaginationInputType!
            $filter: JSONString
        ) {
            reports(
              orderBy: $orderBy,
              pagination: $pagination,
              filter: $filter
            ) {
              data {
                id
                displayId
                createdAt
                updatedAt
                name
                owner {
                  email
                  firstName
                  id
                  lastName
                }
                link {
                  id
                  expirationDate
                  isEnabled
                  isValid
                  isExpired
                  publicUrl
                }
              }
              pagination {
                current
                pageSize
                total
              }
            }
          }
    '''

GET_FILTER_GROUPS_REPORTS = '''
  query FilterGroupsReports {
    filterGroupsReports {
      id
      name
      items {
        id
        name
        subItems {
            id
            name
            disabled
        }
        disabled
      }
    }
  }
'''
