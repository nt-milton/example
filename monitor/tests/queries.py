GET_MONITORS_FILTERS = '''
    query monitorsFilters {
        monitorsFilters {
            id
            category
            items {
                id
                name
            }
        }
    }
    '''
