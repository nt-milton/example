UPDATE_CONTROL_OWNERS = '''
    mutation updateControlOwners($input: UpdateControlInput!) {
      updateControl(input: $input) {
        data {
          id
          ownerDetails {
            email
          }
        }
      }
    }
'''


ADD_CONTROL = '''
  mutation createControl($input: CreateControlInput!) {
    createControl(input: $input) {
      data {
        id
        name
        status
      }
    }
  }
'''

DELETE_CONTROL_EVIDENCE = '''
  mutation deleteControlEvidence($input: DeleteControlEvidenceInput!) {
    deleteControlEvidence(input: $input) {
      deleted
    }
  }
'''

UPDATE_CONTROL_ACTION_ITEM = '''
  mutation ($input: UpdateControlActionItemInput!) {
    updateControlActionItem(input: $input) {
      actionItem {
        id
        name
        description
        completionDate
        dueDate
        isRequired
        isRecurrent
        recurrentSchedule
        status
        metadata
        owner {
          id
          firstName
          email
        }
      }
    }
  }
'''

ADD_CONTROL_ACTION_ITEM = '''
  mutation addControlActionItem($input: AddControlActionItemInput!) {
    addControlActionItem(input: $input) {
      actionItem {
        id
        name
        description
        completionDate
        dueDate
        isRequired
        isRecurrent
        recurrentSchedule
        status
        metadata
        owner {
          id
          firstName
          email
        }
      }
    }
  }
'''

DELETE_CONTROLS = '''
  mutation DeleteControls($input: DeleteControlsInput!) {
    deleteControls(input: $input) {
      success
    }
  }
'''

DELETE_CONTROL = '''
  mutation DeleteControls($input: DeleteControlsInput!) {
    deleteControls(input: $input) {
      success
    }
  }
'''

MIGRATE_ORGANIZATION_TO_MY_COMPLIANCE = '''
  mutation ($payload: MigrateOrganizationPayload!) {
  migrateOrganizationToMyCompliance(payload: $payload) {
    success
  }
}
'''

ADD_CONTROL_EVIDENCE = '''
  mutation addControlEvidence($input: ControlEvidenceInput!) {
    addControlEvidence(input: $input) {
      evidenceIds
      duplicatedIds
      __typename
    }
  }
'''

UPDATE_CONTROL_FAMILY_OWNER = '''
  mutation updateControlFamilyOwner($input: UpdateControlFamilyOwnerInput!){
    updateControlFamilyOwner(input: $input) {
      controlFamilyId
    }
  }
'''

BULK_UPDATE_CONTROL_ACTION_ITEMS = '''
  mutation bulkUpdateControlActionItems($input: UpdateControlActionItemsInput!){
    bulkUpdateControlActionItems(input: $input) {
      actionItems {
        id
        name
        dueDate
        owner {
          email
        }
      }
    }
  }
'''

UPDATE_CONTROL_STATUS = '''
    mutation updateControlStatus($input: UpdateControlInput!) {
      updateControl(input: $input) {
        data {
          id
          status
        }
      }
    }
'''
