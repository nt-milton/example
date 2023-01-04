ADD_OBJECT = '''
    mutation addObject($input: LaikaObjectInput!) {
        createLaikaObject(input: $input) {
          id
          warnings
        }
      }
    '''


GET_LAIKA_OBJECTS = '''
query objects(
    $query: String
    $filter: [LaikaObjectFilterType]
    $orderBy: OrderInputType
    $pagination: PaginationInputType!
  ) {
    objects(query: $query) {
      id
      typeName
      displayName
      iconName
      color
      attributes {
        id
        name
        sortIndex
        attributeType
        Metadata
        minWidth
      }
      elements(filter: $filter, orderBy: $orderBy, pagination: $pagination) {
        pagination {
          current
          pageSize
          total
        }
        data {
          id
          createdAt
          updatedAt
          data
          isManuallyCreated
        }
      }
    }
  }
'''

UPDATE_OBJECT = '''
    mutation updateObject($input: UpdateLaikaObjectInput!) {
        updateLaikaObject(input: $input) {
          id
        }
      }
    '''

BULK_DELETE_OBJECTS = '''
    mutation bulkDeleteLaikaObjects($input: BulkDeleteLaikaObjectsInput!) {
        bulkDeleteLaikaObjects(input: $input) {
          deletedIds
        }
    }
    '''
