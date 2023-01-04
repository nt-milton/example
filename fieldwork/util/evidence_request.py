from evidence.evidence_handler import create_officer_pdf_evidence
from fieldwork.constants import ER_STATUS_DICT, OFFICER_FETCH_TYPE
from fieldwork.models import Attachment, Evidence, EvidenceMetric
from objects.models import LaikaObject, LaikaObjectType
from organization.models import Organization


def update_attachments_status(status: str, attachments: list[Attachment]) -> None:
    attachments_to_update = []
    for attachment in attachments:
        is_invalid_status = status not in [
            ER_STATUS_DICT['Submitted'],
            ER_STATUS_DICT['Auditor Accepted'],
        ]

        if is_invalid_status or attachment.has_been_submitted:
            continue

        attachment.has_been_submitted = True

        attachments_to_update.append(attachment)

    Attachment.objects.bulk_update(attachments_to_update, ['has_been_submitted'])


def file_attachment_match_name(file_name: str, matching_names: list[str]) -> bool:
    return any(name in file_name for name in matching_names)


def store_er_attachments_metrics(
    current_metrics: EvidenceMetric,
    monitors_count: int = 0,
    file_monitors_count: int = 0,
    file_integrations_count: int = 0,
    integrations_category_counter: dict = {},
) -> None:
    total_monitors_count = monitors_count + file_monitors_count

    if total_monitors_count > 0:
        current_metrics.monitors_count = (
            current_metrics.monitors_count + total_monitors_count
        )
        current_metrics.save(update_fields=['monitors_count'])

    if file_integrations_count > 0:
        current_general_count = current_metrics.integrations_counter['general']
        current_metrics.integrations_counter.update(
            {'general': current_general_count + file_integrations_count}
        )
        current_metrics.save()

    if integrations_category_counter:
        current_counter = current_metrics.integrations_counter
        updated_categories_count = {
            key: current_counter.get(key, 0) + value
            for key, value in integrations_category_counter.items()
        }
        current_metrics.integrations_counter.update(updated_categories_count)
        current_metrics.save()


def attach_officers(
    officers: list[str],
    fieldwork_evidence: Evidence,
    organization: Organization,
    time_zone: str,
    ids: list[str],
) -> list[str]:
    if officers:
        officer_pdf, file_name = create_officer_pdf_evidence(
            organization=organization, officer_ids=officers, time_zone=time_zone
        )
        attachment = fieldwork_evidence.add_attachment(
            file_name=file_name, file=officer_pdf, attach_type=OFFICER_FETCH_TYPE
        )
        ids.append(attachment.id)

    return ids


def integration_category_count(
    lo_type: LaikaObjectType, categories_count: dict = {}, general_count: int = 0
):
    laika_object_manual = LaikaObject.objects.filter(
        object_type=lo_type, is_manually_created=True
    ).first()

    laika_object_system = LaikaObject.objects.filter(
        object_type=lo_type, is_manually_created=False
    ).first()

    if not laika_object_manual and not laika_object_system:
        return categories_count, general_count

    if laika_object_manual:
        general_count += 1

    if laika_object_system:
        connection_account = laika_object_system.connection_account

        integration_category = connection_account.integration.category.lower()
        category_count = categories_count.get(integration_category, 0) + 1
        categories_count = {**categories_count, integration_category: category_count}

    return categories_count, general_count


def calculate_er_times_move_back_to_open(evidence_request):
    current_open_transitions = evidence_request.status_transitions.filter(
        to_status=ER_STATUS_DICT['Open']
    ).count()

    return current_open_transitions + 1
