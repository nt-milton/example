CREATE_TRAINING = '''
    mutation createTraining($input: TrainingInput!) {
        createTraining(input: $input) {
            error
            training {
                id
                name
                description
            }
            ok
        }
    }
'''
