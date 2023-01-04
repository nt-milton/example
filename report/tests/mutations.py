CREATE_REPORT = '''
  mutation createReport($input: CreateReportInput!) {
    createReport(input: $input) {
      id
    }
  }
'''

DELETE_REPORT = '''
   mutation toggleReport($input: ToggleReportInput!) {
    toggleReport(input: $input) {
      id
    }
  }
'''
