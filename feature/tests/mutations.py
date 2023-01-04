UPDATE_FEATURE_FLAG = '''
    mutation UpdateFeature($input: UpdateFeatureInput!) {
        updateFeature(input: $input) {
            flags {
                name
                isEnabled
            }
        }
    }
'''
