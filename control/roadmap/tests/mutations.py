UPDATE_CONTROL_GROUP = '''
    mutation updateControlGroup($input: UpdateControlGroupInput!) {
        updateControlGroup(input: $input) {
            controlGroup {
                id
                name
                startDate
                dueDate
            }
        }
    }
'''


UPDATE_CONTROL_GROUP_WEB = '''
    mutation updateControlGroup($input: UpdateControlGroupInput!) {
        updateControlGroupWeb(input: $input) {
            controlGroup {
                id
                name
                startDate
                dueDate
            }
        }
    }
'''


UPDATE_CONTROL_GROUP_SORT_ORDER = '''
    mutation UpdateControlGroupSortOrder(
        $input: UpdateControlGroupSortOrderInput!
    ) {
        updateControlGroupSortOrder(input: $input) {
            success
        }
    }
'''


UPDATE_CONTROL_SORT_ORDER = '''
  mutation UpdateControlSortOrder($input: UpdateControlSortOrderInput!) {
        updateControlSortOrder(input: $input) {
            success
        }
  }
'''

DELETE_GROUP = '''
  mutation deleteControlGroup($input: DeleteGroupInput!) {
    deleteControlGroup(input: $input) {
      success
    }
  }
'''

MOVE_CONTROLS_TO_CONTROL_GROUP = '''
    mutation
        MoveControlsToControlGroup($input: MoveControlsToControlGroupInput!) {
            moveControlsToControlGroup(input: $input) {
                success
            }
        }
'''

CREATE_CONTROL_GROUP = '''
    mutation CreateControlGroup($input: CreateControlGroupInput!) {
        createControlGroup(input: $input) {
            controlGroup {
                name
                sortOrder
                referenceId
            }
        }
    }
'''
