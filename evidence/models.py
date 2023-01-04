import io
import re
import zipfile
from functools import cached_property

import django.utils.timezone as timezone
from django.contrib.postgres.indexes import HashIndex
from django.core.files import File
from django.db import models

import evidence.constants as constants
from laika.storage import PrivateMediaStorage
from laika.utils.dates import now_date
from laika.utils.regex import FILE_NAME_EXTENSION
from laika.utils.zip import zip_file, zip_paper
from link.models import Link
from organization.models import Organization
from policy.models import Policy
from policy.utils.utils import zip_policy
from policy.views import get_published_policy_pdf
from tag.models import Tag
from user.models import User

# TODO: LEGACY_DOCUMENT type can be removed when the legacy evidences
# is deleted from evidence table. It means, that legacy documents will be
# preserved into evidence tables for a while since it can work as historic.
EVIDENCE_TYPE = [
    ('POLICY', 'Policy'),
    ('LEGACY_DOCUMENT', 'Legacy Document'),
    ('FILE', 'File'),
    ('TEAM', 'Team'),
    ('OFFICER', 'Officer'),
    ('LINK', 'Link'),
    ('LAIKA_PAPER', 'Laika Paper'),
]

EXPORT_TYPE = [('DATAROOM', 'Dataroom'), ('DOCUMENTS', 'Documents')]


def evidence_upload_directory(instance, filename):
    return f'{instance.organization.id}/evidence/{instance.id}/{filename}'


def async_export_upload_directory(instance, filename):
    return f'{instance.organization.id}/exports/{instance.id}/{filename}'


def evidence_metadata_attachments_directory_path(instance, filename):
    return f'evidences_metadata/{instance.id}/{filename}'


def get_policy_name(policy, time_zone=None, save_as_pdf=False):
    if save_as_pdf and time_zone:
        date = now_date(time_zone, '%Y_%m_%d_%H_%M')
        return f'{policy.name}_{date}.pdf'
    else:
        return policy.name


class EvidenceQuerySet(models.QuerySet):
    def export(self):
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zf:
            for current in self:
                zip_policy(current, zf)
                zip_file(current, zf)
                zip_paper(current, zf)
        zip_buffer.seek(0)
        return zip_buffer

    def sort(self, order_by):
        if order_by:
            field = 'evidence__' + order_by.get('field')
            return '-' + field if order_by.get('order') == "descend" else field
        else:
            return '-evidence__updated_at'


class EvidenceManager(models.Manager):
    _queryset_class = EvidenceQuerySet

    def custom_create(
        self,
        organization,
        upload_file,
        evidence_type,
        reference_model,
        filters,
        description='',
    ):
        if reference_model.objects.filter(
            **filters, evidence__name=upload_file.name, evidence__type=evidence_type
        ).exists():
            file_ext = re.search(r'(?P<ext>\.[^\/.]+$)', upload_file.name).group('ext')
            file_name_without_ext = re.sub(FILE_NAME_EXTENSION, '', upload_file.name)
            name_regex = f'{file_name_without_ext}\\(\\d+\\)|{file_name_without_ext}'

            counter = (
                reference_model.objects.filter(
                    **filters,
                    evidence__name__regex=name_regex,
                    evidence__type=evidence_type,
                ).count()
                + 1
            )

            # Handles the case to allow test, test(1), test(2), etc
            if counter >= 2:
                counter -= 1

            upload_file.name = f'{file_name_without_ext}({counter}){file_ext}'

        return super().create(
            organization=organization,
            name=upload_file.name,
            description=description,
            type=evidence_type,
            file=upload_file,
        )

    def create_policy(self, organization, policy_id, time_zone=None, save_as_pdf=False):
        policy = Policy.objects.get(organization=organization, id=policy_id)
        evidence, _ = super().get_or_create(
            organization=organization,
            name=get_policy_name(policy, time_zone, save_as_pdf),
            description=policy.description,
            type=constants.POLICY if not save_as_pdf else constants.FILE,
            policy=policy,
        )
        if save_as_pdf:
            evidence.file = File(
                name=evidence.name, file=get_published_policy_pdf(policy.id)
            )
        else:
            evidence.policy = policy
        evidence.save()
        return evidence

    def link_system_evidence(self, evidence, tag):
        return SystemTagEvidence.objects.create(tag=tag, evidence=evidence)

    def link_document(self, organization, document_id, tag):
        evidence = super().get(
            organization=organization,
            id=document_id,
        )
        SystemTagEvidence.objects.create(tag=tag, evidence=evidence)
        return evidence

    def link_legacy_document(self, organization, document_id, tag):
        evidence = super().get(
            organization=organization,
            id=document_id,
        )
        SystemTagLegacyEvidence.objects.get_or_create(tag=tag, evidence=evidence)
        return evidence


class Evidence(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=512)
    description = models.TextField(blank=True)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='evidence'
    )
    tags = models.ManyToManyField(Tag, related_name='evidence', through='TagEvidence')

    system_tags = models.ManyToManyField(
        Tag, related_name='system_evidence', through='SystemTagEvidence'
    )

    system_tags_legacy = models.ManyToManyField(
        Tag, related_name='system_legacy_tag', through='SystemTagLegacyEvidence'
    )

    file = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=evidence_upload_directory,
        max_length=1024,
        null=True,
        blank=True,
    )
    policy = models.ForeignKey(
        Policy, on_delete=models.CASCADE, related_name='evidence', blank=True, null=True
    )
    legacy_document = models.UUIDField(blank=True, null=True)
    type = models.CharField(max_length=20, choices=EVIDENCE_TYPE, blank=True)
    #   This is for documents search purpose
    evidence_text = models.TextField(blank=True, null=True)
    legacy_evidence = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        related_name='migrated_evidence',
        blank=True,
        null=True,
    )

    objects = EvidenceManager()

    class Meta:
        verbose_name_plural = 'evidence'
        permissions = [('rename_evidence', 'Can rename evidence')]
        indexes = [models.Index(fields=['name']), HashIndex(fields=['evidence_text'])]
        constraints = [
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_valid_evidence_type",
                check=models.Q(
                    type__in=[evidence_type[0] for evidence_type in EVIDENCE_TYPE]
                ),
            )
        ]

    @cached_property
    def certificate_tags(self):
        from program.models import SubTask

        subtasks_ids = [tag.name for tag in self.system_tags.all()]
        subtasks_related = SubTask.objects.filter(id__in=subtasks_ids)
        tags = []
        for subtask in subtasks_related:
            tags.extend(subtask.certificates_tags)

        return tags

    def __str__(self):
        return f'Evidence name: {self.name}, type: {self.type}'

    def save(self, *args, **kwargs):
        if self.pk is None:
            if self.file:
                saved_file = self.file
                self.file = None
                super(Evidence, self).save(*args, **kwargs)
                self.file = saved_file

        super(Evidence, self).save()


class TagEvidence(models.Model):
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = 'tags'
        constraints = [
            models.UniqueConstraint(
                fields=['tag', 'evidence'], name='unique_tag_evidence'
            )
        ]

    def __str__(self):
        return self.tag.name


class SystemTagEvidence(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = 'tags'

    def __str__(self):
        return self.tag.name


class Language(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    code = models.CharField(max_length=24)
    evidence = models.ForeignKey(
        Evidence, on_delete=models.CASCADE, related_name='languages'
    )

    def __str__(self):
        return self.code


class IgnoreWordManager(models.Manager):
    def custom_create(
        self,
        organization,
        laika_paper_id,
        evidence_type,
        laika_paper_language,
        laika_paper_ignore_word,
    ):
        evidence = Evidence.objects.get(
            organization=organization, id=laika_paper_id, type=evidence_type
        )
        language, _ = Language.objects.get_or_create(
            evidence=evidence, code=laika_paper_language
        )
        ignore_word, _ = IgnoreWord.objects.get_or_create(
            word=laika_paper_ignore_word, language=language
        )

        return ignore_word


class IgnoreWord(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    word = models.CharField(max_length=512)
    language = models.ForeignKey(
        Language, on_delete=models.CASCADE, related_name='ignore_words'
    )
    objects = IgnoreWordManager()

    def __str__(self):
        return self.word


# TODO: Delete when legacy programs is removed
class SystemTagLegacyEvidence(models.Model):
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)
    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = 'legacy tags'

    def __str__(self):
        return self.tag.name


class AsyncExportRequest(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    link_model = models.OneToOneField(
        Link,
        on_delete=models.CASCADE,
        related_name='async_export_request',
        blank=True,
        null=True,
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='export_requests'
    )
    requested_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='user_export_requests', null=True
    )
    name = models.CharField(
        max_length=100, blank=True, default=''
    )  # Name of the drive or dataroom
    evidence = models.ManyToManyField(
        Evidence, related_name='export_requests', through='AsyncExportEvidence'
    )
    link = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=async_export_upload_directory,
        max_length=2024,
        null=True,
        blank=True,
    )  # Link to evidence zip file
    delivered = models.BooleanField(default=False)
    errors = models.TextField(blank=True)
    export_type = models.CharField(max_length=20, choices=EXPORT_TYPE)
    time_zone = models.CharField(max_length=50, default='US/Eastern')

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="%(app_label)s_%(class)s_valid_export_type",
                check=models.Q(
                    export_type__in=[export_type[0] for export_type in EXPORT_TYPE]
                ),
            )
        ]

    def save(self, *args, **kwargs):
        from .threads import BulkEvidenceExportThread

        evidence_exists = self.id and self.evidence.all().exists()

        if evidence_exists and not self.delivered and not self.link and not self.errors:
            # I had to pass the evidence directly because for some reason
            # it was empty on the request instance in the thread
            export_thread = BulkEvidenceExportThread(self, self.evidence.all())
            export_thread.start()
        super(AsyncExportRequest, self).save(*args, **kwargs)


class AsyncExportEvidence(models.Model):
    evidence = models.ForeignKey(Evidence, on_delete=models.CASCADE)
    export_request = models.ForeignKey(
        AsyncExportRequest, on_delete=models.CASCADE, related_name='export_evidence'
    )
