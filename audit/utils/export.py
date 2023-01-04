import logging
import os
import zipfile
from io import BytesIO
from typing import Dict, List

from bs4 import BeautifulSoup
from django.core.files import File
from openpyxl import Workbook

from audit.models import Audit
from audit.utils.audit import get_current_status, get_report_file
from audit.utils.constants import (
    CRITERIA_HEADERS,
    EVIDENCE_REQUEST_HEADERS,
    REQUIREMENT_HEADERS,
    TESTS_HEADERS,
)
from fieldwork.constants import ER_STATUS_DICT, REQ_STATUS_DICT, TEST_RESULTS
from fieldwork.models import Criteria, CriteriaRequirement, Evidence, Requirement, Test
from laika.aws.ses import send_email
from laika.settings import NO_REPLY_EMAIL
from laika.utils.spreadsheet import (
    add_row_values,
    add_workbook_sheet,
    save_virtual_workbook,
)
from user.models import User

logger = logging.getLogger('audit_utils')

INITIAL_ROW = 2


def map_criteria_row(
    headers: List[Dict[str, str]], criteria: Criteria, extra_filter: dict
):
    criteria_dict = vars(criteria)
    mapped_criteria = {
        header.get('key'): criteria_dict.get(header.get('key', ''), '')
        for header in headers
    }
    if 'requirements' in mapped_criteria:
        requirements = criteria.requirements.filter(
            **extra_filter, is_deleted=False, exclude_in_report=False
        ).values('display_id')

        mapped_criteria['requirements'] = ','.join(
            [req['display_id'] for req in requirements]
        )

    return mapped_criteria


def add_criteria_to_workbook(audit: Audit, workbook: Workbook) -> None:
    criteria_sheet = add_workbook_sheet(
        workbook, sheet_title='criteria', columns_header=CRITERIA_HEADERS
    )
    criteria_ids = CriteriaRequirement.objects.filter(requirement__audit=audit).values(
        'criteria_id'
    )
    criteria = Criteria.objects.filter(id__in=criteria_ids)
    add_row_values(
        criteria_sheet,
        CRITERIA_HEADERS,
        map_criteria_row,
        criteria,
        INITIAL_ROW,
        {'audit_id': audit.id},
    )


def map_requirement_row(headers: List[Dict[str, str]], requirement: Requirement):
    requirement_dict = vars(requirement)
    mapped_requirement = {
        header.get('key'): requirement_dict.get(header.get('key', ''), '')
        for header in headers
    }
    if 'tester' in mapped_requirement:
        tester = (
            requirement.tester.user.get_full_name().title()
            if requirement.tester
            else None
        )

        mapped_requirement['tester'] = tester

    if 'reviewer' in mapped_requirement:
        reviewer = (
            requirement.reviewer.user.get_full_name().title()
            if requirement.reviewer
            else None
        )

        mapped_requirement['reviewer'] = reviewer

    if 'lead_auditor' in mapped_requirement:
        lead_auditor = requirement.audit.lead_auditor
        auditor_name = (
            lead_auditor.get_full_name().title() if lead_auditor else lead_auditor
        )
        mapped_requirement['lead_auditor'] = auditor_name

    if 'evidence_requests' in mapped_requirement:
        evidence_requests = requirement.evidence.filter(
            status=ER_STATUS_DICT['Auditor Accepted']
        ).values('display_id')

        mapped_requirement['evidence_requests'] = ','.join(
            [er['display_id'] for er in evidence_requests]
        )

    if 'tests' in mapped_requirement:
        tests = requirement.tests.all().values('display_id')

        mapped_requirement['tests'] = ','.join([test['display_id'] for test in tests])

    return mapped_requirement


def add_requirement_to_workbook(audit: Audit, workbook: Workbook) -> None:
    requirement_sheet = add_workbook_sheet(
        workbook, sheet_title='requirements', columns_header=REQUIREMENT_HEADERS
    )
    requirements = Requirement.objects.filter(
        audit=audit,
        is_deleted=False,
        exclude_in_report=False,
        status=REQ_STATUS_DICT['Completed'],
    )
    add_row_values(
        requirement_sheet,
        REQUIREMENT_HEADERS,
        map_requirement_row,
        requirements,
        INITIAL_ROW,
    )


def map_test_row(headers: List[Dict[str, str]], test: Test):
    test_dict = vars(test)
    mapped_test = {
        header.get('key'): test_dict.get(header.get('key', ''), '')
        for header in headers
    }
    if 'requirement' in mapped_test:
        mapped_test['requirement'] = test.requirement.display_id

    if 'result' in mapped_test:
        mapped_test['result'] = dict(TEST_RESULTS).get(test.result, '')

    if 'checklist' in mapped_test:
        checklist_html = BeautifulSoup(test.checklist)
        mapped_test['checklist'] = checklist_html.get_text()

    return mapped_test


def add_tests_to_workbook(audit: Audit, workbook: Workbook) -> None:
    test_sheet = add_workbook_sheet(
        workbook, sheet_title='tests', columns_header=TESTS_HEADERS
    )
    tests = Test.objects.filter(
        requirement__audit=audit,
        requirement__is_deleted=False,
        requirement__exclude_in_report=False,
        requirement__status=REQ_STATUS_DICT['Completed'],
    )
    add_row_values(
        test_sheet,
        TESTS_HEADERS,
        map_test_row,
        tests,
        INITIAL_ROW,
    )


def map_evidence_request_row(headers: List[Dict[str, str]], evidence_request: Evidence):
    er_dict = vars(evidence_request)
    mapped_er = {
        header.get('key'): er_dict.get(header.get('key', ''), '') for header in headers
    }
    if 'requirements' in mapped_er:
        requirements = evidence_request.requirements.filter(
            is_deleted=False, exclude_in_report=False
        ).values('display_id')

        mapped_er['requirements'] = ','.join(
            [req['display_id'] for req in requirements]
        )

    return mapped_er


def add_attachments_to_zip(
    evidence_requests: Evidence, zip_folder: zipfile.ZipFile
) -> None:
    for er in evidence_requests:
        er_display_id = er.display_id
        for attachment in er.attachments:
            file_bytes = attachment.file.read()
            file_name = os.path.basename(attachment.file.name)
            attachment_dir = f'{er_display_id}/{file_name}'
            zip_folder.writestr(attachment_dir, file_bytes, zipfile.ZIP_DEFLATED)


def add_evidence_requests_to_workbook(
    audit: Audit, workbook: Workbook, zip_folder: zipfile.ZipFile
) -> None:
    er_sheet = add_workbook_sheet(
        workbook,
        sheet_title='evidence_request',
        columns_header=EVIDENCE_REQUEST_HEADERS,
    )
    ers = Evidence.objects.filter(
        audit=audit, status=ER_STATUS_DICT['Auditor Accepted']
    )
    add_row_values(
        er_sheet,
        EVIDENCE_REQUEST_HEADERS,
        map_evidence_request_row,
        ers,
        INITIAL_ROW,
    )

    add_attachments_to_zip(ers, zip_folder)


def create_audit_zip(audit: Audit, file_name: str) -> BytesIO:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zf:
        workbook = Workbook()

        add_criteria_to_workbook(audit, workbook)
        add_requirement_to_workbook(audit, workbook)
        add_tests_to_workbook(audit, workbook)

        add_evidence_requests_to_workbook(audit, workbook, zf)

        audit_status = audit.status.first()
        current_status = get_current_status(audit_status)

        report = get_report_file(audit=audit, current_status=current_status)

        if report:
            report_name = os.path.basename(report.file.name)
            zf.writestr(report_name, report.file.read())

        sheet_to_delete = workbook['Sheet']
        workbook.remove_sheet(sheet_to_delete)

        zf.writestr(f'{file_name}.xlsx', save_virtual_workbook(workbook))

        zip_buffer.seek(0)
        return zip_buffer


def export_audit_file(audit: Audit, user: User) -> None:
    logger.info(f'Exporting audit {audit.id}')
    organization_name = audit.organization.name
    audit_type = audit.audit_framework_type.audit_type

    file_name = f'{organization_name}_{audit_type}_Audit'
    audit_zip_file = create_audit_zip(audit, file_name)

    audit.exported_audit_file = File(name=f'{file_name}.zip', file=audit_zip_file)
    audit.save()

    context = {'company': organization_name, 'file_link': audit.exported_audit_file.url}
    send_email(
        subject='Your Audit History File is Ready!',
        from_email=NO_REPLY_EMAIL,
        to=[user.email],
        template='audit_history_file_email.html',
        template_context=context,
    )


def export_html_to_plain_text(html: str) -> str:
    soup = BeautifulSoup(html, features='html.parser')
    # Remove all script, style and image elements
    for element in soup(['script', 'style', 'img']):
        element.extract()
    return soup.get_text('\n')
