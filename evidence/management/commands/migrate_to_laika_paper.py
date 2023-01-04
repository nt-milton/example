import traceback

from django.core.management.base import BaseCommand
from django.db import transaction

from drive.models import DriveEvidence
from evidence.constants import FILE, LAIKA_PAPER, LEGACY_DOCUMENT, OFFICER, POLICY, TEAM
from evidence.evidence_handler import create_evidence_pdf
from evidence.models import Evidence, SystemTagLegacyEvidence
from laika.aws.dynamo import get_evidences
from laika.utils.dates import dynamo_timestamp_to_datetime
from organization.models import Organization
from tag.models import Tag
from user.models import User

LEGACY_HTML = 'HTML'

LEGACY_EMPTY = 'EMPTY'


class Command(BaseCommand):
    help = 'Migrate dynamo documents to laika paper'

    def handle(self, *args, **options):
        organizations = Organization.objects.all()
        for organization in organizations:
            self._migrate_organization(organization)

    def _migrate_organization(self, organization):
        log = self.stdout
        log.write('------------------------------------------------------')
        log.write(f'Migration for Organization {organization.name}')
        log.write()

        try:
            with transaction.atomic():
                (
                    ignored,
                    new,
                    existed,
                    doc_tasks,
                    controls,
                    datarooms,
                    vendors,
                ) = self._migrate_documents(organization, log)

                files, ignored_files, file_tasks = self._migrate_files(
                    organization, log
                )

                policies, ignored_policies, policy_tasks = self._migrate_policies(
                    organization, log
                )

                log.write('\nResult:')
                log.write(
                    f'Migrated documents: {new + existed}, '
                    f'Existing documents: {existed}, '
                    f'Ignored dynamo documents: {ignored}, '
                    f'Migrated dataroom papers: {datarooms}, '
                    f'Migrated vendors: {vendors}, '
                    f'Migrated files: {files}, '
                    f'Ignored files: {ignored_files}, '
                    f'Migrated policies: {policies}, '
                    f'Ignored policies: {ignored_policies}, '
                    f'Total new evidence created: {new + files + policies}, '
                    'New Tasks-Evidence tags: '
                    f'{doc_tasks + file_tasks + policy_tasks + controls}'
                )
                log.write('------------------------------------------------------')
        except Exception:
            log.write(f'Migration failed for organization {organization.name}')
            traceback.print_exc()

    @staticmethod
    def _migrate_documents(organization, log):
        (
            ignored,
            new,
            existed,
            tasks_migrated,
            controls_migrated,
            vendors_migrated,
            datarooms_migrated,
        ) = (0, 0, 0, 0, 0, 0, 0)
        documents = get_evidences(str(organization.id))
        log.write(f'Migrating {len(documents)} legacy documents')
        for document in documents:
            evidence, created, tasks, controls, datarooms, vendors = migrate_document(
                organization, document
            )
            if not evidence:
                ignored += 1
            if evidence and created:
                new += 1
            if evidence and not created:
                existed += 1
            tasks_migrated += tasks
            controls_migrated += controls
            datarooms_migrated += datarooms
            vendors_migrated += vendors
        return (
            ignored,
            new,
            existed,
            tasks_migrated,
            controls_migrated,
            datarooms_migrated,
            vendors_migrated,
        )

    @staticmethod
    def _migrate_files(organization, log):
        files_migrated, files_ignored, tasks_migrated = 0, 0, 0
        files = organization.evidence.filter(
            type__in=[FILE, OFFICER, TEAM], legacy_task__isnull=False
        ).distinct()
        log.write(f'Migrating {len(files)} legacy files')
        for file in files:
            tasks = migrate_file(organization, file)
            if tasks == 0:
                files_ignored += 1
            else:
                files_migrated += 1
                tasks_migrated += tasks

        return files_migrated, files_ignored, tasks_migrated

    @staticmethod
    def _migrate_policies(organization, log):
        policies_migrated, policies_ignored, tasks_migrated = 0, 0, 0
        policies = organization.evidence.filter(
            type=POLICY, legacy_task__isnull=False
        ).distinct()
        log.write(f'Migrating {len(policies)} policy evidences')
        for policy in policies:
            tasks = migrate_policy(organization, policy)
            if tasks == 0:
                policies_ignored += 1
            else:
                policies_migrated += 1
                tasks_migrated += tasks

        return policies_migrated, policies_ignored, tasks_migrated


def migrate_document(organization, document):
    new_evidence = dynamo_to_evidence(document)
    new_evidence['organization'] = organization
    legacy_document = new_evidence['legacy_document']
    already_migrated = (
        Evidence.objects.filter(
            legacy_document=legacy_document, organization=organization
        )
        .exclude(type=LEGACY_DOCUMENT)
        .exists()
    )

    if already_migrated:
        return None, None, 0, 0, 0, 0

    evidence, created = Evidence.objects.update_or_create(
        organization=new_evidence['organization'],
        legacy_document=new_evidence['legacy_document'],
        type=new_evidence['type'],
        defaults=new_evidence,
    )

    owner = (
        User.objects.filter(email=document['owner']).first()
        if document.get('owner')
        else None
    )

    DriveEvidence.objects.create(
        drive=organization.drive,
        evidence=evidence,
        is_template=document['is_template'],
        owner=owner,
    )

    tasks_migrated = 0
    controls_migrated = 0
    dataroom_migrated = 0
    vendors_migrated = 0
    if not legacy_document:
        return (
            evidence,
            created,
            tasks_migrated,
            controls_migrated,
            dataroom_migrated,
            vendors_migrated,
        )

    all_legacy_evidences = Evidence.objects.filter(
        legacy_document=legacy_document, organization=organization, type=LEGACY_DOCUMENT
    )

    for legacy_evidence in all_legacy_evidences:
        controls_migrated += migrate_controls(legacy_evidence, evidence)
        dataroom_migrated += migrate_datarooms(organization, evidence, legacy_evidence)
        vendors_migrated += migrate_vendors(organization, evidence, legacy_evidence)

        tasks_migrated = migrate_document_tasks(organization, evidence, legacy_evidence)

    return (
        evidence,
        created,
        tasks_migrated,
        controls_migrated,
        dataroom_migrated,
        vendors_migrated,
    )


def get_pdf_evidence(organization, evidence, legacy_evidence):
    file = create_evidence_pdf(evidence)
    return {
        'file': file,
        'organization': organization,
        'legacy_evidence': legacy_evidence,
        'description': legacy_evidence.description,
        'type': FILE,
        'name': file.name,
    }


def migrate_controls(legacy_evidence, evidence):
    controls = legacy_evidence.controls.all()
    for control in controls:
        control.evidence.add(evidence)
    return len(controls)


def migrate_datarooms(organization, evidence, legacy_evidence):
    datarooms = legacy_evidence.dataroom.all()
    for dataroom in datarooms:
        new_evidence_data = get_pdf_evidence(organization, evidence, legacy_evidence)
        new_evidence = Evidence.objects.create(**new_evidence_data)
        dataroom.evidence.add(new_evidence)
    return len(datarooms)


def migrate_vendors(organization, evidence, legacy_evidence):
    vendors = legacy_evidence.organization_vendor.all()
    for organization_vendor in vendors:
        new_evidence_data = get_pdf_evidence(organization, evidence, legacy_evidence)
        new_evidence = Evidence.objects.create(**new_evidence_data)
        organization_vendor.documents.add(new_evidence)
    return len(vendors)


def migrate_file(organization, legacy_file):
    already_migrated = Evidence.objects.filter(
        legacy_evidence=legacy_file, organization=organization
    ).exists()

    if already_migrated:
        return 0

    new_file = Evidence.objects.create(
        organization=organization,
        name=legacy_file.name,
        description=legacy_file.description,
        file=legacy_file.file,
        type=FILE,
        legacy_document=legacy_file.legacy_document,
        evidence_text=legacy_file.evidence_text,
        created_at=legacy_file.created_at,
        updated_at=legacy_file.updated_at,
        legacy_evidence=legacy_file,
    )

    DriveEvidence.objects.create(drive=organization.drive, evidence=new_file)

    return create_system_tags(new_file, legacy_file, organization)


def migrate_policy(organization, legacy_policy):
    already_migrated = Evidence.objects.filter(
        legacy_evidence=legacy_policy, organization=organization
    ).exists()

    if already_migrated:
        return 0

    new_policy = Evidence.objects.create(
        organization=organization,
        name=legacy_policy.name,
        description=legacy_policy.description,
        file=legacy_policy.file,
        type=legacy_policy.type,
        policy_id=legacy_policy.policy_id,
        created_at=legacy_policy.created_at,
        updated_at=legacy_policy.updated_at,
        legacy_evidence=legacy_policy,
    )

    # Policies should only be tagged and NOT included in DriveEvidence
    return create_system_tags(new_policy, legacy_policy, organization)


def migrate_document_tasks(organization, evidence, legacy_evidence):
    tasks_migrated = 0
    tasks = legacy_evidence.legacy_task.all()
    if len(tasks) > 0:
        evidence.legacy_evidence = legacy_evidence
        evidence.save()
    for task in tasks:
        tag, _ = Tag.objects.get_or_create(organization=organization, name=str(task.id))
        SystemTagLegacyEvidence.objects.get_or_create(tag=tag, evidence=evidence)
        tasks_migrated += 1
    return tasks_migrated


def create_system_tags(evidence, legacy_evidence, organization):
    tasks_migrated = 0
    for task in legacy_evidence.legacy_task.all():
        tag, _ = Tag.objects.get_or_create(organization=organization, name=str(task.id))
        SystemTagLegacyEvidence.objects.get_or_create(tag=tag, evidence=evidence)
        tasks_migrated += 1
    return tasks_migrated


def read_content(document):
    content_type = document['text']['type']
    if content_type == LEGACY_EMPTY:
        return ''
    if content_type == LEGACY_HTML:
        return document['text']['data']
    raise ValueError('Unexpected content type')


def to_date(value):
    return dynamo_timestamp_to_datetime(int(value))


def dynamo_to_evidence(document):
    import io

    from django.core.files import File

    data = read_content(document)
    name = document['name']
    return {
        'legacy_document': document['id'][2:],
        'name': f'{name}.laikapaper',
        'description': document.get('description', ''),
        'created_at': to_date(document['created_at']),
        'updated_at': to_date(document['updated_at']),
        'type': LAIKA_PAPER,
        'file': File(name=f'{name}.laikapaper', file=io.BytesIO(data.encode())),
    }
