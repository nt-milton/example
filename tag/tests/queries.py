GET_TAGS_QUERY = '''
        query (
            $searchCriteria: String,
            $filter: JSONString
        ) {
            tags(
                searchCriteria: $searchCriteria,
                filter: $filter
            ) {
                data {
                    id
                    name
                    organizationName
                }
            }
        }
    '''
