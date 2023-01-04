UPDATE_DASHBOARD_ACTION_ITEM = '''
    mutation($id: String!, $seen: Boolean, $completionDate: String) {
      updateDashboardActionItem(id: $id, seen: $seen,
      completionDate: $completionDate)
        {
            id
            seen
            status
            completionDate,
            dueDate
        }
    }
    '''
