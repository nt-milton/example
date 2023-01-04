from django.db.models import Case, TextField, Value, When

from audit.constants import (
    AUDIT_FRAMEWORK_TYPES,
    AUDIT_STATUS_DEPENDENCIES,
    CURRENT_AUDIT_STATUS,
    TITLE_ROLES,
)


def get_current_status(audit_status):
    if audit_status.completed:
        return CURRENT_AUDIT_STATUS['COMPLETED']

    if audit_status.in_draft_report:
        return CURRENT_AUDIT_STATUS['IN_DRAFT_REPORT']

    if audit_status.fieldwork:
        return CURRENT_AUDIT_STATUS['FIELDWORK']

    if audit_status.initiated:
        return CURRENT_AUDIT_STATUS['INITIATED']

    if audit_status.requested:
        return CURRENT_AUDIT_STATUS['REQUESTED']


def get_report_file(audit, current_status, report_field=None):
    audit_status = audit.status.first()

    if report_field is not None:
        return getattr(audit_status, report_field)

    report = None
    if audit.completed_at:
        report = audit.report

    if current_status == CURRENT_AUDIT_STATUS['IN_DRAFT_REPORT']:
        report = audit_status.draft_report
    elif current_status == CURRENT_AUDIT_STATUS['COMPLETED']:
        report = audit_status.final_report

    return report


def check_if_stage_can_be_enable(audit_status, enable_stage):
    dependencies_to_enable_stage = AUDIT_STATUS_DEPENDENCIES.get(enable_stage.upper())

    if dependencies_to_enable_stage:
        dependencies_values = [
            getattr(audit_status, dependency_field)
            for dependency_field in dependencies_to_enable_stage
        ]
        if not all(dependencies_values):
            raise ValueError(f'Stage {enable_stage} cannot be enable')
    else:
        raise ValueError(f'Invalid audit stage: {enable_stage}')


def get_role_to_assign(role: str) -> str:
    roles_dictionary = dict(TITLE_ROLES)
    return list(roles_dictionary.keys())[list(roles_dictionary.values()).index(role)]


def get_framework_key_by_value(framework_name: str):
    framework_type_keys = dict(AUDIT_FRAMEWORK_TYPES)
    for key, value in framework_type_keys.items():
        if framework_name == value:
            return key


def get_audit_stage_annotate():
    return Case(
        When(status__completed=True, then=Value(CURRENT_AUDIT_STATUS['COMPLETED'])),
        When(
            status__in_draft_report=True,
            then=Value(CURRENT_AUDIT_STATUS['IN_DRAFT_REPORT']),
        ),
        When(status__fieldwork=True, then=Value(CURRENT_AUDIT_STATUS['FIELDWORK'])),
        When(status__initiated=True, then=Value(CURRENT_AUDIT_STATUS['INITIATED'])),
        When(status__requested=True, then=Value(CURRENT_AUDIT_STATUS['REQUESTED'])),
        output_field=TextField(),
    )
