ADD_FILES_DATAROOM = '''
    mutation addFilesToDataroom($input: AddDataroomDocumentsInput!) {
        addFilesToDataroom(input: $input) {
          documentIds
        }
    }
    '''

CREATE_DATAROOM = '''
    mutation createDataroom($input: CreateDataroomInput!) {
        createDataroom(input: $input) {
            data {
                id
            }
        }
    }
'''
