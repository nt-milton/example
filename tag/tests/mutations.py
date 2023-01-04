ADD_NEW_TAG = '''
        mutation addManualTag($input: AddManualTagInput!) {
            addManualTag(input: $input) {
              tagId
            }
        }
'''
