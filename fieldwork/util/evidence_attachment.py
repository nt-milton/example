import io

from django.core.files import File
from openpyxl.writer.excel import save_virtual_workbook

from fieldwork.constants import (
    MONITOR_FETCH_TYPE,
    OBJECT_FETCH_TYPE,
    SOURCE_TYPE_MAPPER,
    YEAR_MONTH_DAY_TIME_FORMAT,
)
from fieldwork.models import Attachment, AttachmentSourceType, Evidence
from laika.utils.dates import now_date
from monitor.export import export_xls
from monitor.models import MonitorInstanceStatus, OrganizationMonitor
from objects.models import LaikaObjectType
from objects.views import write_export_response
from organization.models import Organization

from .evidence_request import integration_category_count


def add_laika_objects_attachments(
    fieldwork_evidence: Evidence,
    objects_ids: list[int],
    organization: Organization,
    time_zone: str,
    general_count: int = 0,
) -> tuple[list[str], dict, int]:
    ids = []
    integrations_category_counter: dict = {}
    for object_type_id in objects_ids:
        file_name, file, laika_object_type = create_file_for_lo(
            organization, object_type_id, time_zone
        )
        attachment = fieldwork_evidence.add_attachment(
            file_name=file_name,
            file=File(name=file_name, file=io.BytesIO(file)),
            attach_type=OBJECT_FETCH_TYPE,
            origin_source_object=laika_object_type,
        )
        ids.append(attachment.id)
        integrations_category_counter, general_count = integration_category_count(
            laika_object_type, integrations_category_counter, general_count
        )
    return ids, integrations_category_counter, general_count


def add_monitors_attachments(
    fieldwork_evidence: Evidence,
    monitors: list[int],
    organization: Organization,
    time_zone: str,
) -> tuple[list[int], int]:
    ids = []
    monitors_count = 0

    filtered_monitors = OrganizationMonitor.objects.filter(
        organization=organization,
        id__in=monitors,
    ).exclude(status=MonitorInstanceStatus.TRIGGERED)
    for org_monitor in filtered_monitors:
        monitor_name = org_monitor.monitor.name
        file_name, file = create_file_for_monitor(
            org_monitor.id, monitor_name, time_zone
        )
        attachment = fieldwork_evidence.add_attachment(
            file_name=file_name,
            file=File(name=file_name, file=file),
            attach_type=MONITOR_FETCH_TYPE,
            origin_source_object=org_monitor.monitor,
        )
        ids.append(attachment.id)
        monitors_count += 1
    return ids, monitors_count


def create_file_for_lo(organization, object_type_id, timezone):
    date = now_date(timezone, YEAR_MONTH_DAY_TIME_FORMAT)
    laika_object_type = LaikaObjectType.objects.get(
        organization=organization, id=object_type_id
    )
    file_name = (
        f'{organization.name.upper()}_{laika_object_type.type_name.upper()}_{date}.xlsx'
    )
    workbook = write_export_response(
        object_type_id,
        [laika_object_type],
    )
    return file_name, save_virtual_workbook(workbook), laika_object_type


def create_file_for_monitor(org_monitor_id, org_monitor_name, timezone):
    date = now_date(timezone, YEAR_MONTH_DAY_TIME_FORMAT)
    file = export_xls(org_monitor_id)
    file_name = f'{org_monitor_name}_{date}.xlsx'
    return file_name, file


def get_attachment_source_type(file_type: str) -> AttachmentSourceType:
    formatted_type = file_type.lower().strip()
    mapped_type = SOURCE_TYPE_MAPPER.get(formatted_type, formatted_type)

    source_type, _ = AttachmentSourceType.objects.get_or_create(name=mapped_type)

    return source_type


def delete_all_evidence_attachments(audit_id, evidence_ids, deleted_by, status=None):
    evidence = Evidence.objects.filter(id__in=evidence_ids, audit__id=audit_id)
    if status:
        evidence = evidence.filter(status=status)
    attachments = Attachment.objects.filter(evidence__in=evidence)
    for attachment in attachments:
        attachment.is_deleted = True
        attachment.deleted_by = deleted_by
    Attachment.objects.bulk_update(attachments, ['is_deleted', 'deleted_by'])
    return evidence
