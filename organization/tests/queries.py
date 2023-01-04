GET_CHECKLIST_BY_NAME = '''
    query checklist($name: String!) {
        checklist(name: $name) {
            actionItem {
                name
            }
            organization {
                name
            }
        }
    }
'''


GET_OFFBOARDING_CHECKLIST = '''
    query offboardingChecklist{
        offboarding {
            actionItem {
                name
            }
            organization {
                name
            }
        }
    }
'''


GET_ROADMAP = '''
    query getOrganizationRoadmap ($filters: RoadmapFilterInputType){
      roadmap (filters: $filters){
        completionDate
        groups {
          id
          name
          dueDate
          progress
          controls {
            id
            name
            health
            status
            groupId
          }
        }
        backlog {
          id
          name
          health
          status
          groupId
        }
      }
    }
'''

GET_ROADMAP_CONTROLS_SUMMARY = '''
    query getOrganizationRoadmapControlsSummary ($filters: RoadmapFilterInputType){
      roadmap (filters: $filters){
        implementedControls
        totalControls
      }
    }
'''

GET_API_TOKENS = '''
   query apiTokens {
       apiTokens{
           name
           id
           createdAt
           expiresAt
           createdBy{
               username
           }
           apiKey
   }
}
'''

DELETE_API_TOKEN = '''
   mutation deleteApiToken($id: Int!) {
        deleteApiToken(id: $id) {
            apiTokenId
        }
    }
'''

GET_ONBOARDING = '''
    query getOnboarding {
        onboarding {
            id
            stateV2
            calendlyUrlV2
            calendlyEventIdV2
            architectMeetingV2
        }
    }
'''

GET_ONBOARDING_EXPERT = '''
    query getOnboardingExpert{
        getOnboardingExpert {
          firstName
          lastName
          email
        }
    }
'''

DELEGATE_ONBOARDING_INTEGRATION = '''
    query delegateOnboardingIntegration(
        $userId: String!,
        $category: String!,
        $vendorId: String
    ) {
        delegateOnboardingIntegration(
            userId: $userId,
            category: $category,
            vendorId: $vendorId
        ) {
            success
            userEmail
        }
    }
'''
