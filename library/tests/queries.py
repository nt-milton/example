GET_LIBRARY_ENTRIES = '''
    query getLibraryEntries(
        $size: Int!
        $page: Int!
        $filters: [String]
        $searchCriteria: String
    ) {
        libraryEntries(
            size: $size
            page: $page
            filters: $filters
            searchCriteria: $searchCriteria
        ) {
            entries {
                answer {
                    _id
                    text
                    shortText
                }
                category
                createdAt
                displayId
                id
                question {
                    text
                    metadata
                }
                aliases
                updatedAt
            }
            page
            totalCount
        }
    }
    '''

GET_QUESTIONNAIRES = '''
    query questionnaires(
        $filter: QuestionnaireFilterInputType!,
        $pagination: PaginationInputType!
        $generateToken: Boolean
    ) {
        questionnaires(
            filter: $filter,
            pagination: $pagination,
            generateToken: $generateToken
        ) {
            questionnaires {
                 id
                 name
                 completed
            }
            pagination {
                page
                pageSize
            }
            apiToken
        }
    }
    '''

GET_QUESTIONNAIRE_DETAILS = '''
    query questionnaireDetails(
            $id: String!,
            $filters: QuestionnaireDetailsFilterType,
            $pagination: PaginationInputType)
    {
        questionnaireDetails(id: $id) {
            questionnaire {
                id
                name
                organization {
                    id
                    name
                }
                questions(filters: $filters, pagination: $pagination) {
                    data {
                        id
                        text
                        libraryEntry {
                            id
                            answer {
                                _id
                                text
                            }
                        }
                        equivalentQuestions {
                            id
                            default
                            text
                        }
                    }
                    pagination {
                        hasNext
                        current
                        pageSize
                        total
                        page
                    }
                }
                progress {
                    percent
                    completed
                    total
                }
            }
        }
    }
    '''


FETCH_EXACT_MATCH = '''
    query fetchDdqAnswers($id: String!, $fetchType: String)
    {
        fetchDdqAnswers(id: $id, fetchType: $fetchType)
        {
            updated{
                text
            }
        }
    }
    '''


FETCH_FUZZY_MATCH = '''
    query fetchDdqAnswers($id: String!, $fetchType: String)
    {
        fetchDdqAnswers(id: $id, fetchType: $fetchType)
        {
            updated{
                text
            }
        }
    }
    '''


GET_QUESTIONNAIRES_FILTERS = '''
    query getQuestionFilters($id: String!) {
        questionFilters(id: $id) {
            id
            category
            items {
                id
                name
            }
        }
    }
    '''


GET_LIBRARY_QUESTIONS = '''
    query getLibraryQuestions(
        $filter: LibraryQuestionsFilterInputType!,
        $pagination: PaginationInputType!,
        $orderBy: [OrderInputType]
    ) {
        libraryQuestions(
            filter: $filter,
            pagination: $pagination,
            orderBy: $orderBy
        ) {
            libraryQuestions {
                id
                text
                completed
                equivalentQuestions {
                    id
                }
            }
            pagination {
                current
                pageSize
                total
                hasNext
            }
            hasLibraryQuestions
        }
    }
    '''


GET_QUESTIONS_WITH_SUGGESTIONS = '''
  query getQuestionsWithSuggestions {
    questionsWithSuggestions {
      suggestions {
        id
        text
        equivalentSuggestions {
            id
        }
      }
      hasSuggestions
    }
  }
'''


GET_LIBRARY_TASKS = '''
  query getLibraryTasks {
    libraryTasks {
      libraryTasks {
        id
        finished
      }
    }
  }
'''
