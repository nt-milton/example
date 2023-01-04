UNPRESCRIBE_CONTROLS = '''
  mutation UnprescribeControls(
    $organizationId: String!
    $controlRefIds: [String]!
  ) {
    unprescribeControls(
      organizationId: $organizationId
      controlRefIds: $controlRefIds
    ) {
      success
    }
  }
'''

PRESCRIBE_CONTROLS = '''
  mutation PrescribeControls(
    $organizationId: String!
    $controlReferenceIds: [String]!
  ) {
    prescribeControls(
      organizationId: $organizationId
      controlRefIds: $controlReferenceIds
    ) {
      success
    }
  }
'''
