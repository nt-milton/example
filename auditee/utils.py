import io
import json
import logging
from typing import Any, Tuple, Union

import pandas
from django.core.files import File
from django.db import connection
from django.db.models import F, Q

from audit.constants import REVIEWERS_AUDITORS_KEY
from audit.models import Audit
from evidence.constants import LAIKA_PAPER
from evidence.evidence_handler import get_document_evidence_name
from evidence.models import Evidence as Documents
from fieldwork.constants import (
    ACCOUNT_OBJECT_TYPE,
    DOCUMENT_FETCH_TYPE,
    LO_RUN,
    LO_SKIP_RUN,
    LO_STILL_RUN,
    MONITOR_FETCH_TYPE,
    OBJECT_FETCH_TYPE,
    OFFICER_FETCH_TYPE,
    OTHER_SOURCE_TYPE,
    POLICY_FETCH_TYPE,
    TEAM_FETCH_TYPE,
    TRAINING_FETCH_TYPE,
    VENDOR_FETCH_TYPE,
    YEAR_MONTH_DAY_TIME_FORMAT,
)
from fieldwork.models import Evidence, EvidenceMetric, FetchLogic, TemporalAttachment
from fieldwork.util.evidence_request import integration_category_count
from fieldwork.utils import bulk_laika_review_evidence
from laika.utils.dates import now_date
from laika.utils.exceptions import ServiceException
from laika.utils.pdf import convert_file_to_pdf, render_template_to_pdf
from monitor.export import export_xls
from monitor.laikaql import build_raw_query
from monitor.models import MonitorInstanceStatus, MonitorResult, OrganizationMonitor
from objects.models import LaikaObjectType
from objects.views import write_fetch_lo_file
from organization.models import Organization
from policy.models import Policy
from policy.views import get_published_policy_pdf
from training.models import Training
from user.constants import AUDITOR_ADMIN
from user.models import Auditor, Officer, Team, User
from user.views import get_officers_pdf, get_team_pdf
from vendor.models import Vendor
from vendor.views import get_vendors_pdf

logger = logging.getLogger('auditee_mutations')


def laika_review_evidence(input, organization=None):
    ev_org_filter_props = {'audit__organization': organization} if organization else {}

    evidence = Evidence.objects.filter(
        id__in=input.get('evidence_ids'),
        audit_id=input.get('audit_id'),
        **ev_org_filter_props,
    )

    updated_evidence = bulk_laika_review_evidence(
        evidence=evidence, review_all=input.get('review_all')
    )
    Evidence.objects.bulk_update(updated_evidence, ['is_laika_reviewed', 'updated_at'])
    ids = [evidence_obj.id for evidence_obj in evidence]
    return ids


def exists_laika_object(organization: Organization, fetch_logic: FetchLogic) -> bool:
    lo_type = fetch_logic.type.partition(OBJECT_FETCH_TYPE)[2]
    return LaikaObjectType.objects.filter(
        organization=organization, type_name=lo_type
    ).exists()


def get_results_from_query(
    organization: Organization, fetch_logic: FetchLogic
) -> Tuple[list[Any], str]:
    if OBJECT_FETCH_TYPE in fetch_logic.type:
        if not exists_laika_object(organization, fetch_logic):
            return [], ''

    query = build_raw_query(organization, fetch_logic.logic['query'])
    with connection.cursor() as cursor:
        cursor.execute(query)
        if OBJECT_FETCH_TYPE in fetch_logic.type:
            res = cursor.fetchall()
            return [
                *res,
            ], query
        else:
            return [item[0] for item in cursor.fetchall()], query


def add_attachment_file_to_evidence(
    evidence: Evidence,
    attachment: TemporalAttachment,
    attach_type: str = OTHER_SOURCE_TYPE,
    origin_source_object=None,
) -> None:
    logger.info(
        f'Adding attachment {attachment.name} to ER '
        f'{evidence.display_id} result from fetch logic '
        f'{attachment.fetch_logic.code}'
    )

    evidence.add_attachment(
        file_name=attachment.name,
        file=File(name=attachment.name, file=attachment.file),
        is_from_fetch=True,
        attach_type=attach_type,
        origin_source_object=origin_source_object,
    )


def create_tmp_attachment(
    fetch_logic: FetchLogic, file_name: str, file: Any
) -> TemporalAttachment:
    return TemporalAttachment.objects.create(
        name=file_name,
        file=File(name=file_name, file=io.BytesIO(file)),
        fetch_logic=fetch_logic,
        audit=fetch_logic.audit,
    )


def create_lo_file(
    organization: Organization, object_type: LaikaObjectType, query: str, timezone: str
):
    date_time = now_date(timezone, YEAR_MONTH_DAY_TIME_FORMAT)
    file_name = (
        f'{organization.name.upper()}_{object_type.type_name.upper()}_{date_time}.xlsx'
    )

    file = write_fetch_lo_file(object_type.id, [object_type], query=query)
    return file_name, file


def delete_repeated_attachments_in_evidence_request(
    ev_request: Evidence, file_name: str
):
    # Attachments from fetch of LO type should be mark as deleted so that they
    # can be replaced by the new fetch run
    ev_request.attachments.all().filter(
        name__startswith=file_name,
        from_fetch=True,
        is_deleted=False,
        has_been_submitted=False,
    ).update(is_deleted=True)


def handle_laika_object_fetch(
    organization: Organization,
    fetch_logic: FetchLogic,
    ev_request: Evidence,
    results: list[str],
    query: str,
    timezone: str,
    integrations_counter: dict = {'general': 0},
) -> None:
    if len(results) == 0:
        if ev_request.run_account_lo_fetch == LO_RUN:
            ev_request.run_account_lo_fetch = LO_SKIP_RUN
            ev_request.save()
        return
    else:
        lo_type = fetch_logic.type.partition(OBJECT_FETCH_TYPE)[2]
        if (
            lo_type == ACCOUNT_OBJECT_TYPE
            and ev_request.run_account_lo_fetch == LO_SKIP_RUN
        ):
            return

        ev_request.run_account_lo_fetch = LO_STILL_RUN
        ev_request.save()
        object_type = LaikaObjectType.objects.get(
            organization=organization, type_name=lo_type
        )
        file_name, file = create_lo_file(organization, object_type, query, timezone)
        lo_file_name = f'{organization.name.upper()}_{object_type.type_name.upper()}_'
        delete_repeated_attachments_in_evidence_request(ev_request, lo_file_name)
        ev_request.add_attachment(
            file_name=file_name,
            file=File(name=file_name, file=io.BytesIO(file)),
            is_from_fetch=True,
            attach_type=OBJECT_FETCH_TYPE,
            origin_source_object=object_type,
        )

        integrations_counter, general_count = integration_category_count(
            object_type, integrations_counter, integrations_counter['general']
        )

        if integrations_counter or general_count:
            EvidenceMetric.objects.filter(evidence_request=ev_request).update(
                integrations_counter={**integrations_counter, 'general': general_count}
            )


def handle_monitors_fetch(
    organization: Organization,
    fetch_logic: FetchLogic,
    ev_request: Evidence,
    results: list[str],
    timezone: str,
    monitors_count: int = 0,
) -> bool:
    org_monitors = OrganizationMonitor.objects.filter(
        monitor_id__in=results, organization=organization
    )
    flagged_monitors_exist = org_monitors.filter(
        status=MonitorInstanceStatus.TRIGGERED
    ).exists()
    filtered_monitors = org_monitors.exclude(status=MonitorInstanceStatus.TRIGGERED)
    for org_monitor in filtered_monitors:
        monitor_result, *_ = MonitorResult.objects.filter(
            organization_monitor=org_monitor
        ).order_by('-id')[:1]
        if len(monitor_result.result.get('data')) > 0:
            file_name, file = create_org_monitor_file(org_monitor, timezone)
            monitor_file_name = f'{org_monitor.monitor.name}_'
            delete_repeated_attachments_in_evidence_request(
                ev_request, monitor_file_name
            )
            attachment = create_tmp_attachment(fetch_logic, file_name, file.read())

            add_attachment_file_to_evidence(
                ev_request,
                attachment,
                attach_type=fetch_logic.type,
                origin_source_object=org_monitor.monitor,
            )
            monitors_count += 1

    EvidenceMetric.objects.filter(evidence_request=ev_request).update(
        monitors_count=monitors_count
    )
    return flagged_monitors_exist


def create_org_monitor_file(
    org_monitor: OrganizationMonitor, timezone: str
) -> Tuple[str, Any]:
    date = now_date(timezone, YEAR_MONTH_DAY_TIME_FORMAT)
    file = export_xls(org_monitor.id)
    file_name = f'{org_monitor.monitor.name}_{date}.xlsx'
    return file_name, file


def create_officers_log_file(officers: list[Officer], timezone: str) -> Tuple[str, Any]:
    pdf = get_officers_pdf(officers, timezone)
    date = now_date(timezone, YEAR_MONTH_DAY_TIME_FORMAT)
    file_name = f'Officers Details_{date}.pdf'
    return file_name, pdf


def handle_officers_log_fetch(
    organization: Organization,
    fetch_logic: FetchLogic,
    evidence: Evidence,
    timezone: str,
) -> None:
    officers = Officer.objects.filter(organization=organization)
    file_name, file = create_officers_log_file(officers, timezone)
    delete_repeated_attachments_in_evidence_request(evidence, 'Officers Details_')
    attachment = create_tmp_attachment(fetch_logic, file_name, file)
    add_attachment_file_to_evidence(evidence, attachment, attach_type=fetch_logic.type)


def create_vendors_log_file(
    organization: Organization, vendors: list[Vendor], timezone: str
) -> Tuple[str, Any]:
    pdf = get_vendors_pdf(organization, vendors, timezone)
    date = now_date(timezone, YEAR_MONTH_DAY_TIME_FORMAT)
    file_name = f'vendors_log_{date}.pdf'
    return file_name, pdf


def handle_vendors_log_fetch(
    organization: Organization,
    fetch_logic: FetchLogic,
    evidence: Evidence,
    timezone: str,
) -> None:
    vendors = organization.organization_vendors.all()
    file_name, file = create_vendors_log_file(organization, vendors, timezone)
    delete_repeated_attachments_in_evidence_request(evidence, 'vendors_log_')
    attachment = create_tmp_attachment(fetch_logic, file_name, file)
    add_attachment_file_to_evidence(evidence, attachment, attach_type=fetch_logic.type)


def get_attachment_type(fetch_logic: FetchLogic) -> str:
    if OBJECT_FETCH_TYPE in fetch_logic.type:
        return OBJECT_FETCH_TYPE

    return fetch_logic.type


def run_fetch_for_other_types(
    organization: Organization,
    ev_request: Evidence,
    fetch_logic: FetchLogic,
    results: list[str],
    query: str,
    timezone: str,
    metrics: dict = {'monitors_count': 0, 'integrations_counter': None},
) -> Union[None, bool]:
    attachments = TemporalAttachment.objects.filter(
        fetch_logic=fetch_logic, audit=fetch_logic.audit
    )
    flagged_monitors_exist = False
    if len(attachments) > 0:
        # If temporal attachments for fetch logic, then no need to recreate
        # the file
        for attachment in attachments:
            attach_type = get_attachment_type(fetch_logic)
            origin_source_object = (
                attachment.policy
                or attachment.document
                or attachment.training
                or attachment.team
            )
            add_attachment_file_to_evidence(
                ev_request,
                attachment,
                attach_type=attach_type,
                origin_source_object=origin_source_object,
            )
    else:
        if OBJECT_FETCH_TYPE in fetch_logic.type:
            integrations_counter = metrics['integrations_counter']
            handle_laika_object_fetch(
                organization,
                fetch_logic,
                ev_request,
                results,
                query,
                timezone,
                integrations_counter,
            )

        if len(results) == 0:
            logger.info(
                f'No attachments added to ER {ev_request.display_id} '
                f'with result of fetch logic {fetch_logic.code}'
            )
            return None

        if fetch_logic.type == MONITOR_FETCH_TYPE:
            monitors_count = metrics['monitors_count']

            flagged_monitors_exist = handle_monitors_fetch(
                organization, fetch_logic, ev_request, results, timezone, monitors_count
            )

        if fetch_logic.type == OFFICER_FETCH_TYPE:
            handle_officers_log_fetch(organization, fetch_logic, ev_request, timezone)

        if fetch_logic.type == VENDOR_FETCH_TYPE:
            handle_vendors_log_fetch(organization, fetch_logic, ev_request, timezone)
    return flagged_monitors_exist


def create_policies_tmp_attachments(audit: Audit, policies: list[Policy]) -> None:
    for policy in policies:
        published_policy_file = get_published_policy_pdf(policy.id)
        if published_policy_file:
            TemporalAttachment.objects.create(
                name=f'{policy.name}.pdf',
                file=File(name=policy.name, file=published_policy_file),
                policy=policy,
                audit=audit,
            )


def create_trainings_tmp_attachments(
    audit: Audit, trainings: list[Training], timezone: str
) -> None:
    for training in trainings:
        pdf = render_template_to_pdf(
            template='training/export_training_log.html',
            context={
                'training': training,
                'members': training.alumni.all(),
            },
            time_zone=timezone,
        )
        name = f'{training.name}-log.pdf'
        TemporalAttachment.objects.create(
            name=name,
            file=File(name=name, file=io.BytesIO(pdf)),
            training=training,
            audit=audit,
        )


def get_evidence_readonly(evidence, time_zone):
    copy_file = File(file=evidence.file, name=evidence.name)
    if evidence.type == LAIKA_PAPER:
        laika_paper_name = get_document_evidence_name(
            copy_file.name, evidence.type, time_zone
        )
        copy_file.file = convert_file_to_pdf(copy_file)
        copy_file.name = f'{laika_paper_name}.pdf'
    return copy_file


def create_documents_tmp_attachments(audit, documents, timezone):
    for ev in documents:
        evidence_readonly = get_evidence_readonly(ev, timezone)
        TemporalAttachment.objects.create(
            name=evidence_readonly.name,
            file=File(name=evidence_readonly.name, file=evidence_readonly),
            document=ev,
            audit=audit,
        )


def create_teams_tmp_attachments(
    audit: Audit, teams: list[Team], timezone: str
) -> None:
    for team in teams:
        team_name = team.name.title()
        pdf = get_team_pdf(team, timezone)
        TemporalAttachment.objects.create(
            name=f'{team_name}.pdf',
            file=File(name=f'{team_name}.pdf', file=io.BytesIO(pdf)),
            team=team,
            audit=audit,
        )


def create_tmp_attachments_for_fk_types(
    organization: Organization, audit: Audit, results: dict, timezone: str
) -> None:
    if len(results[POLICY_FETCH_TYPE]) > 0:
        policies = Policy.objects.filter(
            organization=organization, name__in=results[POLICY_FETCH_TYPE]
        ).distinct()
        create_policies_tmp_attachments(audit, policies)

    if len(results[TRAINING_FETCH_TYPE]) > 0:
        trainings = Training.objects.filter(
            organization=organization, name__in=results[TRAINING_FETCH_TYPE]
        ).distinct()
        create_trainings_tmp_attachments(audit, trainings, timezone)

    if len(results[DOCUMENT_FETCH_TYPE]) > 0:
        documents = Documents.objects.filter(
            organization=organization, name__in=results[DOCUMENT_FETCH_TYPE]
        ).distinct()
        create_documents_tmp_attachments(audit, documents, timezone)

    if len(results[TEAM_FETCH_TYPE]) > 0:
        teams = Team.objects.filter(
            organization=organization, name__in=results[TEAM_FETCH_TYPE]
        ).distinct()
        create_teams_tmp_attachments(audit, teams, timezone)


def delete_audit_tmp_attachments(audit: Audit) -> None:
    TemporalAttachment.objects.filter(audit=audit).delete()


def update_fetch_accuracy_for_evs(ev_requests: list[Evidence]) -> None:
    for ev in ev_requests:
        ev.run_account_lo_fetch = 'run'
        if len(ev.attachments) > 0:
            ev.is_fetch_logic_accurate = True
    Evidence.objects.bulk_update(
        ev_requests, ['is_fetch_logic_accurate', 'run_account_lo_fetch']
    )


def update_description_for_evs(evidence: list[Evidence]) -> None:
    for ev in evidence:
        if not ev.description:
            fetch_logic_descriptions = [
                fetch_logic.description for fetch_logic in ev.fetch_logic.all()
            ]
            description = '\n'.join(x for x in fetch_logic_descriptions if x)
            ev.description = description
    Evidence.objects.bulk_update(evidence, ["description"])


def get_draft_report_alert_and_email_receivers(audit_id: str) -> list[Auditor]:
    audit = Audit.objects.get(id=audit_id)
    audit_firms = [audit.audit_firm]
    query_filter = (
        Q(user__role__iexact=AUDITOR_ADMIN) & Q(audit_firms__in=audit_firms)
    ) | (
        Q(audit_team__title_role__in=REVIEWERS_AUDITORS_KEY)
        & Q(audit_team__audit_id=audit_id)
    )
    return list(Auditor.objects.filter(query_filter).distinct())


def user_in_audit_organization(audit: Audit, user: User) -> bool:
    return audit.organization.id == user.organization.id


def convert_excel_file_to_json(excel_file):
    try:
        if not excel_file.name.endswith('.xlsx'):
            raise ServiceException('Invalid file type. File must be .xlsx')
        excel_data_fragment = pandas.read_excel(excel_file, sheet_name=None)
        excel_data = {}
        for sheet_name in excel_data_fragment:
            sheet_data = excel_data_fragment[sheet_name].to_json()
            excel_data[sheet_name] = sheet_data
        return json.dumps(excel_data)
    except Exception as error:
        raise ValueError('Cannot convert excel file to json', error)


def get_er_metrics_for_fetch(ev_request: Evidence, get_current: bool = False) -> dict:
    current_metrics, _ = EvidenceMetric.objects.get_or_create(
        evidence_request=ev_request, defaults={'integrations_counter': {'general': 0}}
    )
    if get_current:
        return {
            'monitors_count': current_metrics.monitors_count,
            'integrations_counter': current_metrics.integrations_counter,
        }

    return {
        'monitors_count': 0,
        'integrations_counter': {
            # This one doesn't need to be overriten
            'general': current_metrics.integrations_counter['general']
        },
    }


def update_metrics_for_fetch(ev_request: Evidence, metrics: dict, index: int):
    return metrics if index == 0 else get_er_metrics_for_fetch(ev_request, True)


def get_order_by(kwargs, prefix='', default='id'):
    order_by = kwargs.get('order_by')
    if order_by:
        field = f'{prefix}{order_by.get("field")}'
        return (
            F(field).desc(nulls_last=True)
            if order_by.get('order') == 'descend'
            else F(field).asc(nulls_last=True)
        )
    return F(f'{prefix}{default}').asc(nulls_last=True)
