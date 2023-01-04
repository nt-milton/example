LINK_TAGS = '''
    mutation linkTagsToEvidence($input: LinkTagsToEvidenceInput!) {
        linkTags(input: $input) {
            success
        }
    }
'''

UNLINK_TAGS = '''
    mutation unlinkTagsToEvidence($input: LinkTagsToEvidenceInput!) {
        unlinkTags(input: $input) {
            success
        }
    }
'''

UPDATE_EVIDENCE = '''
  mutation updateEvidence($input: EvidenceInput!) {
    updateEvidence(input: $input) {
      success
    }
  }
'''

CREATE_DOCUMENTS = '''
  mutation ($input: ExportRequestInput!){
      asyncExport(input: $input) {
        success
      }
  }
'''
