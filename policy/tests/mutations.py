PUBLISH_POLICY = '''
    mutation publishPolicy($input: PublishPolicyInput!) {
        publishPolicy(input: $input) {
          data {
            id
            isPublished
          }
        }
    }
'''

UNPUBLISH_POLICY = '''
    mutation unpublishPolicy($input: UnpublishPolicyInput!) {
        unpublishPolicy(input: $input) {
          data {
            id
            ok
          }
        }
    }
'''

DELETE_POLICY = '''
    mutation delete_policy($id: [UUID]!) {
        deletePolicy(policyId: $id) {
          success
          error {
            code
            message
          }
        }
    }
'''

BATCH_DELETE_POLICIES = '''
    mutation batchDeletePolicies($policyIds: [UUID]!) {
        deletePolicies(policyIds: $policyIds) {
            error {
                code
                message
            }
            success
        }
    }
'''


UPDATE_IS_DRAFT_EDITED = '''
    mutation UpdateIsDraftEdited($input: UpdateIsDraftEditedInput!) {
      updateIsDrafEdited(input: $input) {
        success
      }
    }
'''


CREATE_POLICY_OR_PROCEDURE = '''
  mutation createPolicy($input: CreatePolicyInput!) {
    createPolicy(input: $input) {
      success
      data {
        id
        name
        isPublished
        policyType
      }
      error {
        code
        message
      }
      permissions
    }
  }
'''


REPLACE_POLICY = '''
  mutation replacePolicy($input: ReplacePolicyInput!) {
      replacePolicy(input: $input) {
        id
      }
  }
'''


UPDATE_NEW_POLICY = '''
 mutation updateNewPolicy($input: UpdateNewPolicyInput!) {
    updateNewPolicy(input: $input) {
      policy {
        id
        owner {
          email
        }
        approver {
          email
        }
      }
    }
  }
'''

UPDATE_POLICY = '''
    mutation updatePolicy($id: UUID!, $input: UpdatePolicyInput!) {
        updatePolicy(id: $id, input: $input) {
            success
            data {
                id
                name
                isPublished
                isRequired
            }
            error {
                code
                message
            }
        }
    }
'''
