GET_ACTION_ITEM_EVIDENCES = '''
  query getActionItemEvidences($id: Int!) {
    actionItemEvidences(id: $id) {
      id
      name
      description
      link
      type: evidenceType
      date
      linkable
      contentId
    }
  }
'''
