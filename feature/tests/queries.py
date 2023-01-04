GET_FEATURE_FLAGS = '''
    query flags {
        flags {
          name
          isEnabled
        }
    }
'''

GET_ALL_FEATURE_FLAGS = '''
    query allFeatureFlags {
        allFeatureFlags {
            name
            displayName
            isEnabled
        }
    }
'''

GET_ALL_AUDITOR_FEATURE_FLAGS = '''
    query auditorFlags {
        auditorFlags {
            name
            isEnabled
        }
    }
'''

GET_AUDITOR_FEATURE_FLAG = '''
    query ($name: String) {
        auditorFlag(name: $name) {
            name
            isEnabled
        }
    }
'''
