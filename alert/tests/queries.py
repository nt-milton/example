GET_NUMBER_NEW_ALERTS = '''
        query getAlerts {
            numberNewAlerts
        }
    '''

GET_CONTROL_NUMBER_NEW_ALERTS = '''
        query getAlerts {
            controlNumberNewAlerts
        }
    '''

GET_AUDITOR_ALERTS = '''
        query getAlerts($pagination: PaginationInputType) {
            auditorAlerts(pagination: $pagination) {
            newAlertsNumber
            alerts {
                id
                alertType
                senderName
                auditType
                firstName
                lastName
            }
            pagination {
                current
                pageSize
                total
                hasNext
            }
            }
        }
    '''

GET_ALERTS = '''
        query getAlerts($pagination: PaginationInputType) {
            alerts(pagination: $pagination) {
              data {
                id
                senderName
                action
                receiverName
                url
                type
                taskName
                policyName
                subtaskGroup
                createdAt
                commentId
                commentState
                auditType
                organizationName
                quantity
                evidenceName
                auditName
                firstName
                lastName
                actionItemDescription
                accessReviewName
              }
              pagination {
                current
                pageSize
                total
                hasNext
              }
            }
        }
    '''
