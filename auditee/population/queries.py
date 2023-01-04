import uuid

import graphene

from audit.models import Audit
from auditee.utils import user_in_audit_organization
from fieldwork.inputs import PopulationDataFilterInput
from fieldwork.types import PopulationCommentType, population_comment_pools_enum
from fieldwork.utils import get_comment_mention_users_by_pool
from laika.decorators import laika_service
from laika.types import OrderInputType, PaginationInputType
from laika.utils.exceptions import ServiceException
from population.models import AuditPopulation, PopulationData
from population.types import (
    AuditPopulationsType,
    AuditPopulationType,
    PopulationCompletenessAccuracyType,
    PopulationConfigurationQuestionType,
    PopulationDataResponseType,
)
from population.utils import (
    get_audit_populations_by_audit_id,
    get_completeness_and_accuracy_files,
    get_population_data,
)
from user.types import UserType


class PopulationQuery(object):
    auditee_audit_population = graphene.Field(
        AuditPopulationType,
        population_id=graphene.String(required=True),
        audit_id=graphene.String(required=True),
    )

    auditee_audit_populations = graphene.Field(
        AuditPopulationsType, audit_id=graphene.String(required=True)
    )

    auditee_population_comments = graphene.List(
        PopulationCommentType,
        audit_id=graphene.String(required=True),
        population_id=graphene.String(required=True),
        pool=graphene.Argument(population_comment_pools_enum, required=True),
    )

    auditee_population_comment_users = graphene.List(
        UserType,
        audit_id=graphene.String(required=True),
        pool=graphene.Argument(population_comment_pools_enum, required=True),
    )

    auditee_population_completeness_accuracy = graphene.List(
        PopulationCompletenessAccuracyType,
        audit_id=graphene.String(required=True),
        population_id=graphene.String(required=True),
    )

    auditee_population_data = graphene.Field(
        PopulationDataResponseType,
        audit_id=graphene.String(required=True),
        population_id=graphene.String(required=True),
        order_by=graphene.Argument(OrderInputType, required=False),
        filters=graphene.List(PopulationDataFilterInput, required=False),
        pagination=graphene.Argument(PaginationInputType, required=False),
    )

    auditee_population_configuration_questions = graphene.List(
        PopulationConfigurationQuestionType,
        audit_id=graphene.String(required=True),
        population_id=graphene.String(required=True),
    )

    @laika_service(
        permission='population.view_auditpopulation',
        exception_msg='Failed to get audit populations.',
        revision_name='Get audit populations',
    )
    def resolve_auditee_audit_populations(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')

        user = info.context.user
        audit = Audit.objects.get(id=audit_id)

        if not user_in_audit_organization(audit, user):
            raise ServiceException(f'User {user.id} cannot get audit populations')

        return get_audit_populations_by_audit_id(audit_id=audit_id)

    @laika_service(
        permission='comment.view_comment',
        exception_msg='Failed to get population comments.',
        revision_name='Get auditee population comments',
    )
    def resolve_auditee_population_comments(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        population_id = kwargs.get('population_id')
        pool = kwargs.get('pool')
        return AuditPopulation.objects.get(
            id=population_id, audit_id=audit_id
        ).get_comments(pool)

    @laika_service(
        permission='population.view_auditpopulation',
        exception_msg='Failed to get population comment users',
        revision_name='Population comment users',
    )
    def resolve_auditee_population_comment_users(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        pool = kwargs.get('pool')
        user_role = info.context.user.role
        return get_comment_mention_users_by_pool(audit_id, pool, user_role)

    @laika_service(
        permission='population.view_populationcompletenessaccuracy',
        exception_msg='Failed to get completeness accuracy files',
        revision_name='Audit population completeness accuracy files',
    )
    def resolve_auditee_population_completeness_accuracy(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        population_id = kwargs.get('population_id')
        return get_completeness_and_accuracy_files(
            audit_id=audit_id, population_id=population_id
        )

    @laika_service(
        permission='population.view_auditpopulation',
        exception_msg='Failed to get population data',
        revision_name='Population data',
    )
    def resolve_auditee_population_data(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        audit = Audit.objects.get(
            id=audit_id,
            organization=info.context.user.organization,
        )
        population_id = kwargs.get('population_id')
        population = AuditPopulation.objects.get(id=population_id, audit_id=audit.id)
        return get_population_data(population.id, kwargs)

    @laika_service(
        permission='population.view_auditpopulation',
        exception_msg='Failed to get population configuration questions',
        revision_name='Population data',
    )
    def resolve_auditee_population_configuration_questions(self, info, **kwargs):
        audit_id = kwargs.get('audit_id')
        audit = Audit.objects.get(
            id=audit_id,
            organization=info.context.user.organization,
        )
        population_id = kwargs.get('population_id')
        population = AuditPopulation.objects.get(id=population_id, audit=audit)
        configuration_questions = population.configuration_questions
        questions = []
        for config in configuration_questions:
            column = config['answer_column']
            operator = None
            answers = (
                PopulationData.objects.values_list(f'data__{column}', flat=True)
                .filter(population_id=population_id)
                .distinct()
            )
            if 'operator' in config and config['type'] == 'DATE_RANGE':
                operator = config['operator']
                answers = [audit.audit_configuration["as_of_date"]]
            questions.append(
                PopulationConfigurationQuestionType(
                    id=uuid.uuid4(),
                    question=config['question'],
                    answers=answers,
                    type=config['type'],
                    column=column,
                    operator=operator,
                )
            )
        return questions
