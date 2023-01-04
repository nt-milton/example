from typing import Any

from django.db.models import QuerySet
from django.template import loader

from auditor.automated_testing.monitor_source import MonitorExcelReader  # noqa: F401
from fieldwork.constants import EVIDENCE_REQUEST_TYPE
from fieldwork.models import Attachment, Evidence, Test

AUTOMATED_TYPES = ['monitor']


class AutomatedTestingProcess:
    def __init__(self, test: Test) -> None:
        self._test = test

    def is_test_automatable(self) -> bool:
        evidence_requests = self._get_evidence_requests()
        return any(
            self._get_evidence_request_automated_attachments(evidence_request).exists()
            for evidence_request in evidence_requests
        )

    def generate_question_answers_html(self) -> str:
        context = {
            "automated_attachments": self._automate_all_evidence_requests(),
            "run_id": self._test.times_run_automate_test + 1,
        }
        template = loader.get_template('questions-answers-template.html')
        return template.render(context)

    def _automate_all_evidence_requests(self) -> list[list]:
        result = list()
        evidence_requests = self._get_evidence_requests()
        for evidence_request in evidence_requests:
            attachments = self._get_evidence_request_automated_attachments(
                evidence_request
            )
            for attachment in attachments:
                result.append(self._apply_template_to_attachment(attachment))
        return result

    def _get_evidence_requests(self) -> list[Evidence]:
        return self._test.requirement.evidence.filter(
            er_type=EVIDENCE_REQUEST_TYPE, is_deleted=False
        )

    def _get_evidence_request_automated_attachments(
        self, evidence_request: Evidence
    ) -> QuerySet[Attachment]:
        return evidence_request.attachment.filter(
            source__name__in=AUTOMATED_TYPES, is_deleted=False
        ).exclude(object_id=None)

    def _get_answer_from_source(self, attachment: Attachment, source: str):
        origin_source_object = attachment.origin_source_object
        local_parameters: dict[str, Any] = dict(
            attachment=attachment, origin_source_object=origin_source_object
        )
        exec(source, globals(), local_parameters)
        return local_parameters.get('answer')

    def _apply_template_to_attachment(self, attachment: Attachment) -> list[dict]:
        template_questions = attachment.source.template
        attachment_source_type = attachment.source.name
        result = list()
        for template_question in template_questions:
            question = template_question['question']
            source = template_question['source']
            answer = self._get_answer_from_source(attachment, source)
            result.append(
                dict(question=question, answer=answer, type=attachment_source_type)
            )
        return result
