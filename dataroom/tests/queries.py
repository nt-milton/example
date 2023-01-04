GET_DATAROOMS = '''
    query getDatarooms($filter: JSONString) {
        datarooms(filter: $filter) {
            id
            name
            owner {
                id
                email
                firstName
                lastName
            }
            updatedAt
            isSoftDeleted
        }
    }
    '''

GET_FILTER_GROUPS = '''
        {
            filterGroupsDatarooms {
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

GET_DATAROOM = '''
    query getDataroom($id: Int!) {
        dataroom(id: $id) {
          id
          evidence {
            id
            name
          }
          name
          updatedAt
        }
    }
'''
