ASSIGN_EVIDENCE = '''
  mutation assignAuditorEvidence($input: AssignEvidenceInput!) {
    assignAuditorEvidence(input: $input) {
      assigned
    }
  }
'''

ASSIGN_AUDITOR_TESTER_REQUIREMENT = '''
        mutation assignAuditorTesterRequirement(
            $input: AssignRequirementInput!
        ) {
            assignAuditorTesterRequirement(input: $input) {
                requirementIds
            }
        }
    '''


ASSIGN_AUDITOR_REVIEWER_REQUIREMENT = '''
        mutation assignAuditorReviewerRequirement(
            $input: AssignRequirementInput!
        ) {
            assignAuditorReviewerRequirement(input: $input) {
                requirementIds
            }
        }
    '''

DELETE_AUDIT_EVIDENCE = '''
    mutation deleteAuditEvidence($input: DeleteAuditEvidenceInput!) {
      deleteAuditEvidence(input: $input) {
        deleted
      }
    }
  '''

DELETE_AUDITOR_REQUIREMENT = '''
    mutation deleteAuditorRequirement($input: DeleteAuditorRequirementInput!) {
      deleteAuditorRequirement(input: $input) {
        deleted
      }
    }
  '''

ADD_AUDITOR_EVIDENCE_ATTACHMENT = '''
  mutation addAuditorEvidenceAttachment($input: AddEvidenceAttachmentInput!) {
    addAuditorEvidenceAttachment(input: $input) {
      documentIds
    }
  }
'''


UPDATE_AUDITOR_EVIDENCE_STATUS = '''
        mutation updateAuditorEvidenceStatus
        ($input: UpdateEvidenceStatusInput!){
            updateAuditorEvidenceStatus(input:$input){
                updated
            }
        }
    '''

RENAME_AUDITOR_EVIDENCE_ATTACHMENT = '''
        mutation
        renameAuditorEvidenceAttachment($input: RenameAttachmentInput!) {
            renameAuditorEvidenceAttachment(input: $input) {
                updated
            }
        }
    '''

UPDATE_AUDITOR_REQUIREMENT_FIELD = '''
        mutation updateAuditorRequirementField(
            $input: UpdateRequirementFieldInput!) {
                updateAuditorRequirementField(input: $input) {
                    requirement {
                        id
                    }
                }
        }
    '''

UPDATE_AUDITOR_REQUIREMENTS_STATUS = '''
    mutation updateAuditorRequirementsStatus(
        $input: UpdateRequirementsStatusInput!
    ) {
      updateAuditorRequirementsStatus(input: $input) {
        updated
      }
    }
  '''

DELETE_AUDITOR_EVIDENCE_ATTACHMENT = '''
        mutation
        deleteAuditorEvidenceAttachment
            ($input: DeleteAuditorEvidenceAttachmentInput!) {
                deleteAuditorEvidenceAttachment(input: $input) {
                attachmentId
            }
        }
    '''

DELETE_AUDITOR_ALL_EVIDENCE_ATTACHMENTS = '''
        mutation
        deleteAuditorAllEvidenceAttachments(
            $input: DeleteAllEvidenceAttachmentInput!) {
            deleteAuditorAllEvidenceAttachments(input: $input) {
                evidence {
                  attachments {
                    id
                    name
                    description
                    createdAt
                  }
                }
            }
        }
    '''


UPDATE_AUDITOR_REQUIREMENT_TEST = '''
        mutation updateAuditorRequirementTest(
            $input: UpdateRequirementTestInput!
        ) {
            updateAuditorRequirementTest(input: $input) {
                testId
            }
        }
    '''

UPDATE_AUDITOR_AUDIT_DRAFT_REPORT_FILE = '''
        mutation updateAuditorAuditDraftReportFile(
            $input: UpdateAuditorAuditDraftReportFileInput!
        ) {
            updateAuditorAuditDraftReportFile(input: $input) {
                name
            }
        }
    '''

UPDATE_EVIDENCE = '''
        mutation updateAuditorEvidence($input: UpdateEvidenceInput!) {
            updateAuditorEvidence(input: $input) {
              evidenceUpdated
            }
          }
      '''

CREATE_AUDITOR_DRAFT_REPORT_REPLY = '''
        mutation createAuditorDraftReportReply(
          $input: CreateDraftReportReplyInput!) {
          createAuditorDraftReportReply(input: $input) {
            reply {
                id
            }
          }
        }
    '''

UPDATE_AUDITOR_DRAFT_REPORT_REPLY = '''
        mutation updateAuditorDraftReportReply(
          $input: UpdateDraftReportReplyInput!) {
          updateAuditorDraftReportReply(input: $input) {
            reply {
                id
            }
          }
        }
    '''

DELETE_AUDITOR_DRAFT_REPORT_REPLY = '''
        mutation deleteAuditorDraftReportReply(
            $input: DeleteDraftReportReplyInput!
        ) {
            deleteAuditorDraftReportReply(input: $input) {
                reply {
                    id
                }
            }
        }
    '''


UPDATE_AUDITOR_AUDIT_DRAFT_REPORT = '''
        mutation updateAuditorAuditDraftReport(
            $input: UpdateAuditorAuditDraftReportInput!
        ) {
            updateAuditorAuditDraftReport(input: $input) {
            audit {
                id
                name
                draftReport{
                name
                url
                }
            }
            }
        }
    '''

UPDATE_DRAFT_REPORT_COMMENT_STATE = '''
        mutation updateAuditorDraftReportCommentState(
          $input: UpdateDraftReportCommentStateInput!) {
            updateAuditorDraftReportCommentState(input: $input) {
                draftReportComment {
                    comment {
                        id,
                        content,
                        state
                    },
                    page
                }
            }
        }
    '''

CREATE_AUDITOR_REQUIREMENT = '''
        mutation createAuditorRequirement(
            $input: AddAuditorRequirementInput!
        ) {
            createAuditorRequirement(input: $input) {
                  requirement {
                        displayId
                  }
            }
        }
    '''

UPDATE_AUDITOR_REQUIREMENT = '''
        mutation updateAuditorRequirement(
            $input: UpdateAuditorRequirementInput!
        ) {
            updateAuditorRequirement(input: $input) {
                requirement {
                    id
                }
            }
        }
    '''

ADD_AUDITOR_EVIDENCE_REQUEST = '''
        mutation addAuditorEvidenceRequest(
            $input: AddAuditorEvidenceRequestInput!
        ) {
            addAuditorEvidenceRequest(input: $input) {
                evidence {
                    id
                    name
                    displayId
                    requirements {
                        id
                        name
                    }
                    instructions
                }
            }
        }
    '''

UPDATE_AUDITOR_EVIDENCE_REQUEST = '''
        mutation updateAuditorEvidenceRequest(
            $input: UpdateAuditorEvidenceRequestInput!
        ) {
            updateAuditorEvidenceRequest(input: $input) {
                evidence {
                    id
                    name
                    displayId
                    instructions
                    requirements {
                        id
                        name
                    }
                }
            }
        }
    '''

DELETE_AUDITOR_REQUIREMENT_TEST = '''
    mutation deleteAuditorRequirementTest($testId: ID!) {
        deleteAuditorRequirementTest(testId: $testId) {
            test {
                id
                displayId
                name
            }
        }
    }
'''

CREATE_AUDITOR_REQUIREMENT_TEST = '''
    mutation createAuditorRequirementTest(
        $input: CreateRequirementTestInput!
    ) {
        createAuditorRequirementTest(input: $input) {
            test {
                id
                displayId
                name
            }
        }
    }
'''

UPDATE_AUDITOR_POPULATION = '''
    mutation updateAuditorAuditPopulation(
        $input: UpdatePopulationInput!
    ) {
        updateAuditorAuditPopulation(input: $input) {
            population {
                id
                timesMovedBackToOpen
                status
                configurationFilters
            }
        }
    }
'''


CREATE_AUDITOR_POPULATION_SAMPLE = '''
    mutation createAuditorPopulationSample(
        $input: CreateAuditorPopulationSampleInput!
    ) {
        createAuditorPopulationSample(input: $input) {
            populationData {
                id
            }
        }
    }
'''


CREATE_AUDITOR_SAMPLE_SIZE = '''
    mutation createAuditorSampleSize(
        $input:PopulationInput!
    ) {
        createAuditorSampleSize(input: $input) {
            population {
                id
                sampleSize
            }
        }
    }
'''


UPDATE_AUDITOR_AUDIT_REPORT_SECTION = '''
    mutation UpdateAuditorAuditReportSection(
        $input: UpdateAuditorAuditReportSectionInput!
    ) {
        updateAuditorAuditReportSection(input: $input) {
            audit {
                id
                draftReportSections {
                    name
                    url
                    fileName
                    section
                }
            }
        }
    }
'''

DELETE_AUDITOR_POPULATION_SAMPLE = '''
    mutation deleteAuditorPopulationSample(
        $input: DeleteAuditorAuditPopulationInput!
    ) {
        deleteAuditorPopulationSample(input: $input) {
            samples {
                id
            }
        }
    }
'''

ADD_AUDITOR_POPULATION_SAMPLE = '''
    mutation addAuditorPopulationSample(
        $input: PopulationInput!
    ) {
        addAuditorPopulationSample(input: $input) {
            sample {
                id
            }
        }
    }
    '''
UPDATE_AUDITOR_COMPLETENESS_ACCURACY = '''
  mutation UpdateAuditorPopulationCompletenessAccuracy(
    $input: UpdatePopulationCompletenessAccuracyInput!
  ) {
    updateAuditorPopulationCompletenessAccuracy(input: $input) {
      completenessAccuracy {
        id
        name
        url
        populationId
      }
    }
  }
'''

DELETE_AUDITOR_COMPLETENESS_ACCURACY = '''
  mutation DeleteAuditorPopulationCompletenessAccuracy(
    $input: DeletePopulationCompletenessAccuracyInput!
  ) {
    deleteAuditorPopulationCompletenessAccuracy(input: $input) {
      completenessAccuracy {
        id
        name
        url
        populationId
      }
    }
  }
'''

ATTACH_SAMPLE_TO_EVIDENCE_REQUEST = '''
 mutation AttachSampleToEvidenceRequest(
    $input: PopulationInput!
) {
    attachSampleToEvidenceRequest(input: $input) {
        evidenceRequest {
            id
        }
    }
}
'''


UPDATE_AUDITOR_DRAFT_REPORT_SECTION_CONTENT = '''
        mutation updateAuditorDraftReportSectionContent(
            $input: UpdateDraftReportSectionContentInput!
        ) {
            updateAuditorDraftReportSectionContent(input: $input) {
                name
            }
        }
    '''


PUBLISH_AUDITOR_REPORT_VERSION = '''
    mutation publishAuditorReportVersion(
        $input: PublishAuditorReportVersionInput!
    ) {
        publishAuditorReportVersion(input: $input) {
            success
        }
    }
'''

ADD_AUDITOR_COMMENT = '''
    mutation addAuditorComment($input: AddCommentInput!) {
        addAuditorComment(input: $input) {
            comment {
                id
            }
        }
    }
'''

UPDATE_AUDITOR_COMMENT = '''
    mutation updateAuditorComment($input: UpdateCommentInput!) {
        updateAuditorComment(input: $input) {
            comment {
                id
            }
        }
    }
'''

ADD_AUDITOR_REPLY = '''
    mutation addAuditorReply($input: AddReplyInput!) {
        addAuditorReply(input: $input) {
            reply {
                id
            }
        }
    }
'''

UPDATE_AUDITOR_REPLY = '''
    mutation updateAuditorReply($input: UpdateReplyInput!) {
        updateAuditorReply(input: $input) {
            reply {
                id
            }
        }
    }
'''

DELETE_AUDITOR_COMMENT = '''
    mutation deleteAuditorComment($input: DeleteCommentInput!) {
        deleteAuditorComment(input: $input) {
            comment {
                id
            }
        }
    }
'''

DELETE_AUDITOR_REPLY = '''
mutation deleteAuditorReply($input: DeleteReplyInput!) {
    deleteAuditorReply(input: $input) {
        reply {
            id
        }
    }
}
'''

UPDATE_CRITERIA = '''
  mutation updateAuditorCriteria(
    $input: UpdateAuditorCriteriaInput!
  ) {
    updateAuditorCriteria(input: $input) {
      criteria {
        id
        description
        isQualified
      }
    }
  }
'''

AUTOMATE_AUDITOR_REQUIREMENT_TEST = '''
  mutation automateAuditorRequirementTest(
    $input: AutomateRequirementTestInput!
  ) {
    automateAuditorRequirementTest(input: $input) {
      test {
        id
        displayId
        name
        automatedChecklist
        isAutomated
      }
    }
  }
'''
