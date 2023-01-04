GET_BLUEPRINT_CONTROLS = '''
    query getBlueprintControls(
        $organizationId: String!
        $pagination: PaginationInputType
        $orderBy: OrderInputType
        $filter: [ControlBlueprintFilterType]
        $searchCriteria: String
    ) {
        blueprintControls(
            organizationId: $organizationId
            pagination: $pagination
            orderBy: $orderBy
            filter: $filter
            searchCriteria: $searchCriteria
        ) {
            data {
                id
                referenceId
                name
                description
                isPrescribed
                family {
                    id
                    name
                }
                allCertifications {
                    id
                    displayName
                }
            }
            pagination {
                pageSize
                page
            }
        }
    }
'''

GET_ALL_BLUEPRINT_CONTROLS = '''
    query getBlueprintControls(
        $organizationId: String!
        $filter: [ControlBlueprintFilterType]
        $searchCriteria: String
    ) {
        allBlueprintControls(
            organizationId: $organizationId
            filter: $filter
            searchCriteria: $searchCriteria
        ) {
            data {
                id
                referenceId
                isPrescribed
            }
        }
    }
'''


GET_BLUEPRINT_CONTROL_STATUS = '''
    query BlueprintControlStatus {
        response: blueprintControlStatus {
            id
            category
            items {
            id
            name
            }
        }
    }
'''
