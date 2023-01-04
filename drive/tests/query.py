GET_LAIKA_LOGS = '''
        query getLaikaLogs(
            $searchCriteria: String
            $orderBy: OrderInputType
            $pagination: PaginationInputType
        ) {
            laikaLogs(
                searchCriteria: $searchCriteria
                orderBy: $orderBy
                pagination: $pagination
            ) {
                laikaLogs {
                    id
                    name
                    source
                }
                pagination {
                    current
                    pageSize
                    total
                }
            }
        }
    '''

GET_DOCUMENT_FILTERS_QUERY = '''
        query getDocumentsFilters {
          driveFilters {
            data {
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

GET_FILTERED_DOCUMENTS_QUERY = '''
        query($orderBy: OrderInputType, $filters: FiltersDocumentType) {
          filteredDrives(
            orderBy: $orderBy
            filters: $filters
          ) {
            id
            organizationName
            collection {
              id
              name
              type
              createdAt
              updatedAt
              extension
              description
            }
          }
        }
    '''
