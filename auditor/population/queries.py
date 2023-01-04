import graphene

from audit.models import Audit
from auditor.utils import is_auditor_associated_to_audit_firm
from fieldwork.inputs import PopulationDataFilterInput
from fieldwork.types import PopulationCommentType, population_comment_pools_enum
from laika.decorators import audit_service
from laika.types import OrderInputType, PaginationInputType
from laika.utils.exceptions import ServiceException
from population.models import AuditPopulation
from population.types import (
    AuditPopulationsType,
    AuditPopulationType,
    PopulationCompletenessAccuracyType,
    PopulationDataResponseType,
)
from population.utils import (
    get_audit_populations_by_audit_id,
    get_completeness_and_accuracy_files,
    get_population_data,
)


class PopulationQuery(object):
    auditor_audit_populations = graphene.Field(
        AuditPopulationsType, audit_id=graphene.String(required=True)
    )

    auditor_audit_population = graphene.Field(
        AuditPopulationType,
        population_id=graphene.String(required=True),
        audit_id=graphene.String(required=True),
    )

    auditor_population_completeness_accuracy = graphene.List(
        PopulationCompletenessAccuracyType,
        audit_id=graphene.String(required=True),
        population_id=graphene.String(required=True),
    )

    auditor_population_data = graphene.Field(
        PopulationDataResponseType,
        audit_id=graphene.String(required=True),
        population_id=graphene.String(required=True),
        is_sample=graphene.Boolean(),
        order_by=graphene.Argument(OrderInputType, required=False),
        filters=graphene.List(PopulationDataFilterInput, required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
        search_criteria=graphene.String(required=False),
    )

    auditor_population_comments = graphene.List(
        PopulationCommentType,
        audit_id=graphene.String(required=True),
        population_id=graphene.String(required=True),
        pool=graphene.Argument(population_comment_pools_enum, required=True),
    )

    @audit_service(
        permission='population.view_auditpopulation',
        exception_msg='Auditor failed to get audit populations.',
        revision_name='Get audit populations',
    )
    def resolve_auditor_audit_populations(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        auditor_id = info.context.user.id
        audit = Audit.objects.get(id=audit_id)

        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=auditor_id):
            raise ServiceException(
                f'Auditor with id: {audit_id} can not '
                f'get populations for audit {audit_id}'
            )

        return get_audit_populations_by_audit_id(audit_id=audit_id)

    @audit_service(
        permission='population.view_auditpopulation',
        exception_msg='Failed to get audit population.',
        revision_name='Get audit population',
    )
    def resolve_auditor_audit_population(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        population_id = kwargs.get('population_id')

        audit = Audit.objects.get(id=audit_id)

        if not is_auditor_associated_to_audit_firm(
            audit=audit, auditor_id=info.context.user.id
        ):
            raise ServiceException(
                f'Auditor can not view audit population for audit {audit_id}'
            )

        return AuditPopulation.objects.get(audit__id=audit_id, id=population_id)

    @audit_service(
        permission='population.view_populationcompletenessaccuracy',
        exception_msg='Failed to get completeness accuracy files',
        revision_name='Audit population completeness accuracy files',
    )
    def resolve_auditor_population_completeness_accuracy(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        population_id = kwargs.get('population_id')
        auditor_id = info.context.user.id
        audit = Audit.objects.get(id=audit_id)
        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=auditor_id):
            raise ServiceException(
                f'Auditor with id: {auditor_id} can not '
                'get completeness and accuracy files '
                f'for audit {audit_id}'
            )
        return get_completeness_and_accuracy_files(
            audit_id=audit_id, population_id=population_id
        )

    @audit_service(
        permission='population.view_auditpopulation',
        exception_msg='Failed to get population data',
        revision_name='Population data',
    )
    def resolve_auditor_population_data(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        audit = Audit.objects.get(
            id=audit_id,
        )
        if not is_auditor_associated_to_audit_firm(
            audit=audit, auditor_id=info.context.user.id
        ):
            raise ServiceException(
                f"You're not allowed view population data for audit {audit_id}"
            )
        population_id = kwargs.get('population_id')
        population = AuditPopulation.objects.get(id=population_id, audit_id=audit.id)
        return get_population_data(population.id, kwargs)

    @audit_service(
        permission='comment.view_comment',
        exception_msg='Failed to get population comments.',
        revision_name='Get auditor population comments',
    )
    def resolve_auditor_population_comments(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        population_id = kwargs.get('population_id')
        pool = kwargs.get('pool')
        audit_firm = info.context.user.auditor.audit_firms.first()
        return AuditPopulation.objects.get(
            id=population_id, audit_id=audit_id, audit__audit_firm__in=[audit_firm]
        ).get_comments(pool)
