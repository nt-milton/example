ADD_ACTION_ITEM_EVIDENCE = '''
  mutation addActionItemEvidence($input: ActionItemEvidenceInput!) {
    addActionItemEvidence(input: $input) {
      evidences {
        id
        name
        description
        type: evidenceType
      }
    }
  }
'''


DELETE_ACTION_ITEM_EVIDENCE = '''
  mutation deleteActionItemEvidence($input: DeleteActionItemEvidenceInput!) {
    deleteActionItemEvidence(input: $input) {
      evidences {
        id
        name
        description
        type: evidenceType
      }
    }
  }
'''
