import json

import pytest

from auditor.automated_testing.automated_testing import AutomatedTestingProcess
from fieldwork.constants import MONITOR_SOURCE_TYPE
from fieldwork.models import AttachmentSourceType, Evidence
from monitor.models import Monitor

MONITOR_NAME_QUESTION = "Monitor name:"
MONITOR_PURPOSE_QUESTION = "Monitor purpose:"
CONCLUSION_AFTER_REVIEW_QUESTION = "Conclusion after review:"
EXCLUDED_RESOURCES_QUESTION = "Excluded resources:"
FLAG_RESOURCES_QUESTION = "Flag resources:"

EXPECTED_MONITOR_RESULT = [
    [
        {
            "question": MONITOR_NAME_QUESTION,
            "answer": "Evidence monitor healthy test",
            "type": "monitor",
        },
        {
            "question": MONITOR_PURPOSE_QUESTION,
            "answer": "Evidence monitor healthy test test",
            "type": "monitor",
        },
        {
            "question": CONCLUSION_AFTER_REVIEW_QUESTION,
            "answer": None,
            "type": "monitor",
        },
        {
            "question": EXCLUDED_RESOURCES_QUESTION,
            "answer": "None excluded",
            "type": "monitor",
        },
        {
            "question": FLAG_RESOURCES_QUESTION,
            "answer": "None returned for that violations section",
            "type": "monitor",
        },
    ],
    [
        {
            "question": MONITOR_NAME_QUESTION,
            "answer": "Exception monitor healthy test",
            "type": "monitor",
        },
        {
            "question": MONITOR_PURPOSE_QUESTION,
            "answer": "Exception monitor healthy test test",
            "type": "monitor",
        },
        {
            "question": CONCLUSION_AFTER_REVIEW_QUESTION,
            "answer": None,
            "type": "monitor",
        },
        {
            "question": EXCLUDED_RESOURCES_QUESTION,
            "answer": "3 exclusions",
            "type": "monitor",
        },
        {
            "question": FLAG_RESOURCES_QUESTION,
            "answer": "No resources flagged",
            "type": "monitor",
        },
    ],
]


@pytest.fixture
def automated_testing_process(not_tested_test):
    return AutomatedTestingProcess(test=not_tested_test)


@pytest.fixture
def monitor_attachment_source_type(attachment_source_types):
    source_type = AttachmentSourceType.objects.get(name=MONITOR_SOURCE_TYPE)
    source_type.template = [
        {
            "question": MONITOR_NAME_QUESTION,
            "source": "answer = origin_source_object.name",
        },
        {
            "question": MONITOR_PURPOSE_QUESTION,
            "source": "answer = origin_source_object.description",
        },
        {"question": CONCLUSION_AFTER_REVIEW_QUESTION, "source": ""},
        {
            "question": EXCLUDED_RESOURCES_QUESTION,
            "source": (
                "excluded_results_count ="
                " MonitorExcelReader(attachment.file).count_items_on_sheet('Excluded"
                " Results')\nanswer = f'{excluded_results_count} exclusions' if"
                " origin_source_object.health_condition == 'empty_results' and"
                " excluded_results_count > 0 else 'None excluded'"
            ),
        },
        {
            "question": FLAG_RESOURCES_QUESTION,
            "source": (
                "flagged_results_count ="
                " MonitorExcelReader(attachment.file).count_items_on_sheet('Last"
                " Result')\nexception_monitor_answer = f'{flagged_results_count}"
                " flagged' if flagged_results_count > 0 else 'No resources"
                " flagged'\nanswer = exception_monitor_answer if"
                " origin_source_object.health_condition == 'empty_results' else 'None"
                " returned for that violations section'"
            ),
        },
    ]
    source_type.save()
    return source_type


@pytest.mark.functional
def test_automate_all_evidence_requests(
    automated_testing_process: AutomatedTestingProcess,
    evidence_with_monitor_attachments: Evidence,
):
    assert json.dumps(
        automated_testing_process._automate_all_evidence_requests()
    ) == json.dumps(EXPECTED_MONITOR_RESULT)


@pytest.mark.functional
def test_get_evidence_requests(
    automated_testing_process: AutomatedTestingProcess,
    evidence_with_monitor_attachments: Evidence,
):
    result = automated_testing_process._get_evidence_requests()
    assert len(result) == 1
    assert result[0].id == evidence_with_monitor_attachments.id


@pytest.mark.functional
def test_get_evidence_request_automated_attachments(
    automated_testing_process: AutomatedTestingProcess,
    evidence_with_monitor_attachments: Evidence,
):
    result = automated_testing_process._get_evidence_request_automated_attachments(
        evidence_with_monitor_attachments
    )
    assert len(result) == 2


@pytest.mark.functional
def test_get_answer_from_source(
    automated_testing_process: AutomatedTestingProcess,
    evidence_with_monitor_attachments: Evidence,
    monitor_attachment_source_type: AttachmentSourceType,
    healthy_evidence_monitor: Monitor,
):
    attachment = automated_testing_process._get_evidence_request_automated_attachments(
        evidence_with_monitor_attachments
    )[0]
    assert (
        automated_testing_process._get_answer_from_source(
            attachment, monitor_attachment_source_type.template[0].get('source')
        )
        == healthy_evidence_monitor.name
    )


@pytest.mark.functional
def test_apply_template_to_attachment(
    automated_testing_process: AutomatedTestingProcess,
    evidence_with_monitor_attachments: Evidence,
):
    attachment = automated_testing_process._get_evidence_request_automated_attachments(
        evidence_with_monitor_attachments
    )[0]
    assert (
        automated_testing_process._apply_template_to_attachment(attachment)
        == EXPECTED_MONITOR_RESULT[0]
    )


@pytest.mark.functional
def test_requirement_test_is_automated(
    automated_testing_process: AutomatedTestingProcess,
    evidence_with_monitor_attachments: Evidence,
):
    assert automated_testing_process.is_test_automatable()


@pytest.mark.functional
def test_requirement_test_is_not_automated(
    automated_testing_process: AutomatedTestingProcess,
):
    assert not automated_testing_process.is_test_automatable()


@pytest.mark.functional
def test_generate_question_answers_html_for_monitors(
    automated_testing_process: AutomatedTestingProcess,
    evidence_with_monitor_attachments: Evidence,
):
    template_html = automated_testing_process.generate_question_answers_html()
    assert template_html
    assert 'None excluded' in template_html
    assert 'None returned for that violations section' in template_html
    assert 'No resources flagged' in template_html
    assert '3 exclusions' in template_html
    assert 'Run #1' in template_html
