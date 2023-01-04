import logging

import evidence.constants as constants
from evidence.evidence_handler import (
    create_file_evidence,
    create_officer_evidence,
    create_team_evidence,
    get_copy_source_file,
    get_files_to_upload,
    increment_file_name,
    reference_evidence_exists,
)
from evidence.models import Evidence
from vendor.models import OrganizationVendorEvidence

logger = logging.getLogger('vendor_evidence_handler')


def create_vendor_evidence(
    organization, organization_vendor, evidence_file, evidence_type=constants.FILE
):
    filters = {'organization_vendor': organization_vendor}
    if reference_evidence_exists(
        OrganizationVendorEvidence, evidence_file.name, evidence_type, filters
    ):
        evidence_file = increment_file_name(
            OrganizationVendorEvidence, evidence_file, evidence_type, filters
        )
    evidence = create_file_evidence(organization, evidence_file)
    organization_vendor.documents.add(evidence)
    return evidence


def upload_vendor_file(organization, files, organization_vendor):
    ids = []
    if not files:
        return ids
    upload_files = get_files_to_upload(files)
    for file in upload_files:
        evidence = create_vendor_evidence(organization, organization_vendor, file)
        ids.append(evidence.id)
    return ids


def add_vendor_other_evidence(organization, other_evidence_paths, organization_vendor):
    ids = []
    if not other_evidence_paths:
        return ids
    for other_evidence_path in other_evidence_paths:
        evidence_source_file = get_copy_source_file(organization, other_evidence_path)
        evidence = create_vendor_evidence(
            organization, organization_vendor, evidence_source_file, constants.FILE
        )
        ids.append(evidence.id)
    return ids


def add_vendor_officers(organization, officers, organization_vendor, time_zone):
    ids = []
    if not officers:
        return ids
    for officer in officers:
        evidence = create_officer_evidence(organization, officer, time_zone)
        add_evidence_to_vendor(organization_vendor, evidence)
        ids.append(evidence.id)
    return ids


def add_vendor_teams(organization, teams, organization_vendor, time_zone):
    ids = []
    if not teams:
        return ids
    for team_id in teams:
        evidence = create_team_evidence(organization, team_id, time_zone)
        add_evidence_to_vendor(organization_vendor, evidence)
        ids.append(evidence.id)
    return ids


def add_vendor_policy(organization, policies, organization_vendor):
    ids = []
    if not policies:
        return ids
    for policy in policies:
        evidence = Evidence.objects.create_policy(organization, policy)
        add_evidence_to_vendor(organization_vendor, evidence)
        ids.append(evidence.id)
    return ids


def add_evidence_to_vendor(organization_vendor, evidence):
    organization_vendor.documents.add(evidence)
    logger.info(evidence)


def delete_evidence(organization, evidence_ids, organization_vendor):
    OrganizationVendorEvidence.objects.filter(
        evidence__id__in=evidence_ids,
        evidence__organization=organization,
        organization_vendor=organization_vendor,
    ).delete()
