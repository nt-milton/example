CREATE_CONCIERGE_REQUEST = '''
  mutation createConciergeRequest(
    $input: ConciergeRequestInput!
  ) {
    createConciergeRequest(input: $input) {
      conciergeRequest {
        id
        description
      }
    }
  }
'''
