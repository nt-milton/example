DELETE_CHECKLIST_STEP = '''
    mutation deleteChecklistStep($checklistId: Int!, $input: [Int]!) {
        deleteChecklistStep(checklistId: $checklistId, input: $input) {
            success
        }
    }
'''

UPDATE_CHECKLIST_STEP = '''
    mutation UpdateCheckListStep(
        $id: Int,
        $name: String,
        $description: String!,
        $metadata: JSONString,
        $parentActionItem: Int
    ) {
        updateChecklistStep(
            id: $id,
            name: $name,
            parentActionItem: $parentActionItem,
            metadata: $metadata,
            description: $description
        ){
            checkListStep {
            id
            name
            description
            metadata
            }
        }
    }
'''

CREATE_CHECKLIST_TAG = '''
    mutation CreateChecklistTag(
        $checklistId: Int!,
        $name: String!,
        $stepId: Int!
    ) {
        createChecklistTag(
            checklistId: $checklistId,
            name: $name,
            stepId: $stepId,
        ){
            tag {
                id
                name
            }
        }
    }
'''

USE_TEMPLATE_CHECKLIST = '''
    mutation useTemplateChecklist($checklistId: Int!) {
    useTemplateChecklist(checklistId: $checklistId) {
        checklist {
            name
            description
            metadata
            }
        }
    }
'''

CREATE_CHECKLIST_RUN = '''
    mutation createChecklistRun(
        $checklistName: String!,
        $userId: String!
    ) {
        createChecklistRun(checklistName: $checklistName, userId: $userId) {
            checklistRun {
                id
                createdAt
                owner {
                    email
                }
                offboardingRun {
                    nonIntegratedVendors {
                        offboardingState {
                            id
                            status
                            date
                        }
                        vendor {
                            id
                            name
                        }
                    }
                }
            }
        }
    }
'''

UPDATE_CHECKLIST_RESOURCE_MUTATION = '''
    mutation UpdateChecklistRunResource($ids: [Int], $date: Date,
    $status: String, $resourceType: String!, $checklistRun: Int!) {
        updateChecklistRunResource(ids: $ids, date: $date, status:
        $status, resourceType: $resourceType,
        checklistRun: $checklistRun) {
            checklistResources {
                id
                date
                status
            }
        }
    }
'''

UPDATE_CHECKLIST_RUN = '''
     mutation updateChecklistRun(
    $checklistRunId: Int!
    $date: Date!
    $metadata: String!
  ) {
    updateChecklistRun(
      checklistRunId: $checklistRunId
      date: $date
      metadata: $metadata
    ) {
      checklistRun{
          id
          date
          metadata
      }
    }
  }
'''


RUN_ACCESS_SCAN = '''
  mutation RunAccessScan($userId: String!, $vendorIds: [String]!) {
    runAccessScan(userId: $userId, vendorIds: $vendorIds) {
      success
    }
  }
'''

CREATE_API_TOKEN = '''
  mutation createApiToken($name: String!){
     createApiToken(name:$name){
       id
       token
    }
  }
'''

MOVE_ORG_OUT_OF_ONBOARDING = '''
    mutation MoveOrgOutOfOnboarding(
      $input: MoveOrgOutOfOnboardingInput!
    ) {
        moveOrgOutOfOnboarding(input: $input) {
            success
        }
    }
'''

SUBMIT_ONBOARDING_V2_FORM = '''
mutation submitOnboardingV2Form($responseId: String){
    submitOnboardingV2Form(responseId: $responseId) {
        success
        error {
            code
            message
        }
    }
}
'''

COMPLETE_ONBOARDING = '''
mutation completeOnboarding {
    completeOnboarding {
      success
      error {
        code
        message
      }
    }
  }
'''

UPDATE_ONBOARDING_V2_STATE = '''
mutation updateOnboardingV2State($stateV2: String) {
    updateOnboardingV2State(stateV2: $stateV2) {
      success
      error {
        code
        message
      }
    }
  }
'''

BOOK_ONBOARDING_MEETING = '''
mutation bookOnboardingMeeting($eventId: String!, $inviteeId: String!) {
    bookOnboardingMeeting(eventId: $eventId, inviteeId: $inviteeId) {
      onboarding {
        id
        calendlyEventIdV2
        calendlyInviteeIdV2
      }
    }
  }
'''

VALIDATE_ONBOARDING_MEETING = '''
mutation validateOnboardingMeeting {
    validateOnboardingMeeting {
      onboarding {
        id
        architectMeetingV2
        calendlyInviteeIdV2
      }
    }
  }
'''
