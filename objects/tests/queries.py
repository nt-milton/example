GET_OBJECTS = '''
        query objects($query: String) {
            objects(query: $query) {
                id
                typeName
                description
                displayName
                color
                iconName
                __typename
            }
        }
    '''

GET_LAIKA_OBJECT_BY_ID = '''
query object(
    $id: String,
    $objectType: String,
  ) {
    object(id: $id, objectType: $objectType) {
      id
      createdAt
      updatedAt
      data
      isManuallyCreated
    }
  }
'''

GET_OBJECT_TYPES_PAGINATED = '''
  query getObjectsPaginated(
    $pagination: PaginationInputType!
    $orderBy: OrderInputType
    $searchCriteria: String
  ) {
    objectsPaginated(
      pagination: $pagination
      orderBy: $orderBy
      searchCriteria: $searchCriteria
    ) {
      objects {
        id
        typeName
        description
        displayName
        color
        iconName
      }
      pagination {
        current
        pageSize
        total
      }
    }
  }
'''
