import math

import graphene
from django.db.models import Q
from graphene_django.types import DjangoObjectType

from audit.utils.data_detected import get_data_detected
from fieldwork.models import Requirement
from fieldwork.types import EvidenceRequirementType, FieldworkEvidenceType
from fieldwork.utils import get_comments_count, get_display_id_order_annotation
from laika.types import BulkUploadType, FileType, PaginationResponseType
from population.models import AuditPopulation, PopulationComment, PopulationData


class PopulationDataType(graphene.ObjectType):
    class Meta:
        model = PopulationData

    id = graphene.String()
    data = graphene.JSONString()
    is_sample = graphene.Boolean()


class AuditPopulationType(DjangoObjectType):
    class Meta:
        model = AuditPopulation
        fields = (
            'id',
            'name',
            'instructions',
            'description',
            'pop_type',
            'source_info',
            'display_id',
            'default_source',
            'sample_size',
            'times_moved_back_to_open',
        )

    evidence_request = graphene.List(FieldworkEvidenceType)
    requirements = graphene.List(EvidenceRequirementType)
    status = graphene.String()
    data_file = graphene.Field(FileType)
    data_file_name = graphene.String()
    comments_counter = graphene.Int()
    selected_source = graphene.String()
    configuration_seed = graphene.List(graphene.JSONString)
    configuration_saved = graphene.List(graphene.JSONString)
    column_types = graphene.JSONString()
    configuration_filters = graphene.JSONString()
    population_data_counter = graphene.Int()
    laika_source_data_detected = graphene.JSONString()
    selected_default_source = graphene.String()
    recommended_sample_size = graphene.Int()

    def resolve_laika_source_data_detected(self, info):
        sources = self.default_source.split(',')
        return {source: get_data_detected(self, source) for source in sources}

    def resolve_status(self, info):
        return self.status

    def resolve_evidence_request(self, info):
        order_annotate = {
            'display_id_sort': get_display_id_order_annotation(preffix='ER-')
        }
        return (
            self.evidence_request.all()
            .annotate(**order_annotate)
            .order_by('display_id_sort')
        )

    def resolve_requirements(self, info):
        requirements = Requirement.objects.filter(
            evidence__in=self.evidence_request.all()
        ).distinct()

        related_requirements = [
            EvidenceRequirementType(
                id=requirement.id,
                name=requirement.name,
                display_id=requirement.display_id,
                description=requirement.description,
                supporting_evidence=requirement.evidence,
                tester=requirement.tester,
                reviewer=requirement.reviewer,
                criteria=requirement.criteria,
                last_edited_at=requirement.last_edited_at,
            )
            for requirement in requirements
        ]

        return related_requirements

    def resolve_data_file(self, info):
        if self.data_file:
            return FileType(name=self.data_file.name, url=self.data_file.url)
        return None

    def resolve_comments_counter(self, info):
        user_role = info.context.user.role
        param_filter = Q(population=self)
        return get_comments_count(PopulationComment, user_role, param_filter)

    def resolve_column_types(self, info):
        from .utils import get_column_types

        return get_column_types(self.display_id, self.selected_source)

    def resolve_population_data_counter(self, info):
        filters = self.get_query_filters()
        return (
            PopulationData.objects.filter(population_id=self.id).filter(filters).count()
        )

    def resolve_configuration_seed(self, info):
        return self.configuration_questions

    def resolve_recommended_sample_size(self, info):
        population_filters = self.get_query_filters()
        population_count = self.population_data.filter(population_filters).count()
        sample_size = math.floor(population_count * 0.25)
        return sample_size if sample_size > 0 else 1


class AuditPopulationsType(graphene.ObjectType):
    open = graphene.List(AuditPopulationType)
    # submitted groups both submitted and accepted
    submitted = graphene.List(AuditPopulationType)


class PopulationCompletenessAccuracyType(FileType):
    population_id = graphene.Int()

    def resolve_url(self, info):
        return self.file.url


class PopulationBulkUploadType(BulkUploadType):
    success = graphene.Boolean()
    audit_population = graphene.Field(AuditPopulationType)


class PopulationDataResponseType(graphene.ObjectType):
    population_data = graphene.List(PopulationDataType)
    pagination = graphene.Field(PaginationResponseType)


class PopulationConfigurationQuestionType(graphene.ObjectType):
    id = graphene.String()
    question = graphene.String()
    answers = graphene.List(graphene.String)
    type = graphene.String()
    column = graphene.String()
    operator = graphene.String()


class LaikaSourcePopulationResponseType(graphene.ObjectType):
    population_data = graphene.List(PopulationDataType)
    errors = graphene.Boolean()


class ManualSourcePopulationResponseType(graphene.ObjectType):
    population_data = graphene.List(PopulationDataType)
