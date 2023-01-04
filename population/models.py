from django.db import models

from audit.models import Audit
from audit.utils.incredible_filter import get_incredible_filter
from comment.models import Comment
from fieldwork.constants import ALL_POOL, COMMENTS_POOLS
from fieldwork.models import Evidence
from laika.storage import PrivateMediaStorage
from laika.utils.exceptions import ServiceException

from .constants import (
    POPULATION_DEFAULT_SOURCE,
    POPULATION_SOURCE,
    POPULATION_SOURCE_DICT,
    POPULATION_STATUS,
    POPULATION_STATUS_DICT,
    POPULATION_TYPE,
)


def population_templates_directory_path(instance, filename):
    return f'population/templates/{instance.id}/{filename}'


def population_files_directory_path(instance, filename):
    return f'population/{instance.id}/{filename}'


class Population(models.Model):
    class Meta:
        abstract = True

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    display_id = models.CharField(max_length=50)
    name = models.CharField(max_length=500)
    default_source = models.CharField(max_length=200)
    instructions = models.TextField(blank=True, null=True)
    pop_type = models.CharField(max_length=50, choices=POPULATION_TYPE)


class Sample(models.Model):
    name = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    evidence_request = models.ForeignKey(Evidence, on_delete=models.CASCADE, null=True)
    population_data = models.ForeignKey(
        'PopulationData', on_delete=models.CASCADE, null=True
    )

    def __str__(self):
        return self.name


class PopulationSource(models.Model):
    # In case a LO is selected, store which type
    # of LO was selected (Change Request, Event, etc)
    selected_source_display_name = models.CharField(max_length=200)
    selected_source_icon = models.CharField(max_length=200)
    selected_source_color = models.CharField(max_length=200)


class AuditPopulation(Population):
    class Meta:
        unique_together = (('display_id', 'audit'),)

    audit = models.ForeignKey(
        Audit, related_name='populations', on_delete=models.CASCADE
    )
    description = models.TextField()
    status = models.CharField(max_length=50, choices=POPULATION_STATUS, default='open')
    evidence_request = models.ManyToManyField(
        Evidence, related_name='populations', through='AuditPopulationEvidence'
    )
    selected_source = models.CharField(max_length=50, choices=POPULATION_SOURCE)
    selected_default_source = models.CharField(
        max_length=50, choices=POPULATION_DEFAULT_SOURCE, null=True, blank=True
    )
    source_info = models.ForeignKey(
        PopulationSource,
        related_name='population',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    # In case of manual upload, to have the original file available.
    data_file_name = models.CharField(max_length=255, blank=True)
    data_file = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=population_files_directory_path,
        max_length=512,
        null=True,
        blank=True,
    )
    # snapshot of raw_data with applied filters.
    data_snapshot = models.JSONField(blank=True, null=True)
    filters = models.JSONField(blank=True, null=True)
    sample_logic = models.TextField(blank=True, null=True)
    sample_size = models.IntegerField(blank=True, null=True)
    # Used for manual pop configuration
    configuration_seed = models.JSONField(blank=True, null=True)
    # Used for laika source pop configuration
    laika_source_configuration = models.JSONField(blank=True, null=True)
    samples = models.ManyToManyField(
        Sample, related_name='populations', through='AuditPopulationSample'
    )
    times_moved_back_to_open = models.IntegerField(default=0)
    configuration_saved = models.JSONField(blank=True, null=True)
    configuration_filters = models.JSONField(blank=True, null=True)

    @property
    def configuration_questions(self):
        configuration_questions = (
            self.configuration_seed
            if self.selected_source == POPULATION_SOURCE_DICT['manual']
            else self.laika_source_configuration
        )

        return configuration_questions if configuration_questions else []

    def get_comments(self, pool: str) -> list:
        from comment.types import BaseCommentType
        from fieldwork.types import PopulationCommentType

        comments = []
        population_comments = self.comments.filter(
            pool=pool, comment__is_deleted=False
        ).order_by('comment__created_at')
        for population_comment in population_comments:
            comment = population_comment.comment
            filtered_replies = comment.replies.filter(is_deleted=False).order_by(
                'created_at'
            )
            replies = [
                BaseCommentType(
                    id=reply.id,
                    owner=reply.owner,
                    owner_name=reply.owner_name,
                    content=reply.content,
                    created_at=reply.created_at,
                    updated_at=reply.updated_at,
                )
                for reply in filtered_replies
            ]
            comments.append(
                PopulationCommentType(
                    id=comment.id,
                    owner=comment.owner,
                    owner_name=comment.owner_name,
                    content=comment.content,
                    created_at=comment.created_at,
                    updated_at=comment.updated_at,
                    is_deleted=comment.is_deleted,
                    state=comment.state,
                    pool=population_comment.pool,
                    replies=replies,
                )
            )

        return comments

    def update_status(self, new_status: str):
        self.track_times_moved_back_to_open(new_status)

        self.status = new_status
        self.save()

    def track_times_moved_back_to_open(self, new_status: str) -> int:
        if (
            new_status == POPULATION_STATUS_DICT['Open']
            and self.status != POPULATION_STATUS_DICT['Open']
        ):
            self.times_moved_back_to_open = self.times_moved_back_to_open + 1
            self.save()
        return self.times_moved_back_to_open

    def get_query_filters(self):
        transformed_filters = (
            [
                {
                    'field': population_filter.get('column'),
                    'value': population_filter.get('value'),
                    'operator': population_filter.get('condition'),
                    'type': population_filter.get('columnType'),
                }
                for population_filter in self.configuration_filters
            ]
            if self.configuration_filters
            else []
        )
        population_filters = get_incredible_filter(
            {'filters': transformed_filters}, 'data__'
        )
        return population_filters


class PopulationCompletenessAccuracy(models.Model):
    name = models.CharField(max_length=200)
    is_deleted = models.BooleanField(default=False)
    population = models.ForeignKey(
        AuditPopulation, on_delete=models.CASCADE, related_name='completeness_accuracy'
    )
    file = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to=population_files_directory_path,
        max_length=512,
        null=True,
        blank=True,
    )

    def update_name(self, new_name):
        if (
            PopulationCompletenessAccuracy.objects.filter(
                population_id=self.population_id,
                population__audit_id=self.population.audit_id,
                name=new_name,
            )
            .exclude(id=self.id)
            .exists()
        ):
            raise ServiceException(
                'This file name already exists. Use a different name.'
            )
        self.name = new_name
        self.save()


class AuditPopulationEvidence(models.Model):
    population = models.ForeignKey(
        AuditPopulation,
        on_delete=models.CASCADE,
    )
    evidence_request = models.ForeignKey(
        Evidence,
        on_delete=models.CASCADE,
    )


class AuditPopulationSample(models.Model):
    population = models.ForeignKey(AuditPopulation, on_delete=models.CASCADE)
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE)


class PopulationCommentManager(models.Manager):
    def custom_create(self, owner, content, population_id, tagged_users, pool=ALL_POOL):
        comment = Comment.objects.create(owner=owner, content=content)

        population = AuditPopulation.objects.get(
            pk=population_id,
        )

        population_comment_data = {
            'population': population,
            'comment': comment,
        }

        if pool:
            population_comment_data['pool'] = pool

        population_comment = super().create(**population_comment_data)

        comment.add_mentions(tagged_users)

        return population_comment.comment


class PopulationComment(models.Model):
    population = models.ForeignKey(
        AuditPopulation, on_delete=models.CASCADE, related_name='comments'
    )
    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, related_name='population'
    )
    pool = models.CharField(max_length=10, choices=COMMENTS_POOLS, null=True)

    objects = PopulationCommentManager()


class PopulationData(models.Model):
    data = models.JSONField(blank=True, null=True)
    population = models.ForeignKey(
        AuditPopulation, on_delete=models.CASCADE, related_name='population_data'
    )
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    evidence_request = models.ManyToManyField(
        Evidence, related_name='population_sample', through='sample'
    )

    @staticmethod
    def remove_sample(population_id):
        sample = PopulationData.objects.filter(
            is_sample=True, population__id=population_id
        )

        for population_data in sample:
            population_data.is_sample = False

        PopulationData.objects.bulk_update(sample, ['is_sample'])
