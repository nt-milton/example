CREATE_NEW_QUESTIONNAIRE = '''
  mutation createQuestionnaireEntry($name: String!) {
    createQuestionnaireEntry(name: $name) {
      questionnaire {
        id
        name
        organization
      }
    }
  }
'''

BULK_UPDATE_QUESTIONNAIRE_STATUS = '''
        mutation bulkUpdateQuestionnaireStatus
        ($input: BulkUpdateQuestionnaireStatusInput!){
            bulkUpdateQuestionnaireStatus(input:$input){
                updated
            }
        }
    '''

DELETE_QUESTIONNAIRE = '''
        mutation deleteQuestionnaire
        ($input: DeleteQuestionnairesInput!) {
            deleteQuestionnaire(input: $input) {
                deleted
            }
        }
    '''

CREATE_QUESTIONNAIRE_QUESTIONS = '''
    mutation CreateQuestionnaireQuestions(
        $input: CreateQuestionnaireQuestionInput!
    ) {
        createQuestionnaireQuestions(input: $input) {
          questions {
            id
            text
            metadata
            libraryEntry {
              id
              answer {
                _id
                text
              }
            }
          }
        }
      }
'''

DELETE_QUESTIONNAIRE_QUESTIONS = '''
        mutation deleteQuestionnaireQuestions
        ($input: DeleteQuestionnaireQuestionsInput!) {
            deleteQuestionnaireQuestions(input: $input) {
                deletedIds
                updated {
                    id
                }
            }
        }
    '''

UPDATE_QUESTION_ASSIGNED_USER = '''
    mutation updateQuestionAssignedUser
    ($input: UpdateQuestionAssignedUserInput!) {
        updateQuestionAssignedUser(input: $input) {
            question
        }
    }
    '''

UPDATE_LIBRARY_QUESTION_STATUS = '''
        mutation updateLibraryQuestionStatus
        ($input: UpdateLibraryQuestionStatusInput!){
            updateLibraryQuestionStatus(input: $input){
                updated
            }
        }
    '''

ADD_EQUIVALENT_QUESTION = '''
        mutation addEquivalentQuestion($input: EquivalentQuestionInput!) {
            addEquivalentQuestion(input: $input) {
                updated
            }
        }
    '''

REMOVE_EQUIVALENT_QUESTION = '''
        mutation removeEquivalentQuestion($input: EquivalentQuestionInput!) {
            removeEquivalentQuestion(input: $input) {
                updated
        }
    }
    '''

UPDATE_QUESTION_ANSWER = '''
        mutation updateQuestionAnswer
        ($input: UpdateQuestionAnswerInput!){
            updateQuestionAnswer(input: $input){
                updated
            }
        }
    '''

UPDATE_LIBRARY_QUESTION = '''
        mutation updateLibraryQuestion
        ($input: UpdateLibraryQuestionInput!){
            updateLibraryQuestion(input: $input){
                updated
            }
        }
    '''

DELETE_LIBRARY_QUESTION = '''
        mutation deleteLibraryQuestion
        ($input: DeleteLibraryQuestionInput!){
            deleteLibraryQuestion(input: $input){
                deleted
            }
        }
    '''

RESOLVE_EQUIVALENT_SUGGESTION = '''
        mutation resolveEquivalentSuggestion
        ($input: ResolveEquivalentSuggestionInput!){
            resolveEquivalentSuggestion(input: $input){
                resolved
            }
        }
    '''


BULK_LIBRARY_UPLOAD = '''
  mutation bulkLibraryUpload($input: LibraryFileInput!) {
    bulkLibraryUpload(input: $input) {
      uploadResult {
        successRows {
          id
        }
        failedRows {
          type
          addresses
        }
      }
    }
  }
'''


ADD_DOCUMENTS_QUESTIONNAIRE_DATAROOM = '''
    mutation addDocumentsQuestionnaireDataroom (
        $input: AddDocumentsQuestionnaireDataroomInput!
    ) {
        addDocumentsQuestionnaireDataroom(input: $input) {
          documentIds
        }
    }
    '''
