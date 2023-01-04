import math

import graphene

from audit.models import Audit
from auditor.inputs import (
    CreateAuditorPopulationSampleInput,
    DeleteAuditorAuditPopulationInput,
)
from auditor.utils import is_auditor_associated_to_audit_firm
from fieldwork.constants import ER_TYPE
from fieldwork.inputs import (
    DeletePopulationCompletenessAccuracyInput,
    UpdatePopulationCompletenessAccuracyInput,
    UpdatePopulationInput,
)
from fieldwork.types import FieldworkEvidenceType
from laika.decorators import audit_service
from laika.utils.exceptions import ServiceException
from population.inputs import PopulationInput
from population.models import (
    AuditPopulation,
    PopulationCompletenessAccuracy,
    PopulationData,
    Sample,
)
from population.types import (
    AuditPopulationType,
    PopulationCompletenessAccuracyType,
    PopulationDataType,
)
from population.utils import set_sample_name


class UpdateAuditorAuditPopulation(graphene.Mutation):
    class Arguments:
        input = UpdatePopulationInput(required=True)

    population = graphene.Field(AuditPopulationType)

    @audit_service(
        permission='population.change_auditpopulation',
        exception_msg='Failed to update population',
        revision_name='Update population',
    )
    def mutate(self, info, input):
        audit_id = input.get('audit_id')
        population_id = input.get('population_id')
        user = info.context.user
        audit = Audit.objects.get(id=audit_id)
        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException("Auditor can not update population")

        audit_population = AuditPopulation.objects.get(
            audit_id=audit_id, id=population_id
        )

        update_fields = []
        for input_field in input.fields:
            field = input_field.field
            value = input_field.value
            json_list = input_field.json_list
            if field == 'status':
                audit_population.update_status(new_status=input_field.value)
            else:
                update_fields.append(field)
                val = value if value else json_list
                setattr(audit_population, field, val)
        audit_population.save(update_fields=update_fields)
        return UpdateAuditorAuditPopulation(population=audit_population)


class UpdateAuditorPopulationCompletenessAndAccuracy(graphene.Mutation):
    class Arguments:
        input = UpdatePopulationCompletenessAccuracyInput(required=True)

    completeness_accuracy = graphene.Field(PopulationCompletenessAccuracyType)

    @audit_service(
        permission='population.change_populationcompletenessaccuracy',
        exception_msg='Failed to update completeness accuracy',
        revision_name='Update population completeness accuracy',
    )
    def mutate(self, info, input):
        completeness_accuracy_id = input.id
        audit_id = input.audit_id
        population_id = input.population_id
        new_name = input.new_name
        user = info.context.user

        audit = Audit.objects.get(id=audit_id)
        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException(
                'Auditor can not update name for completeness accuracy file'
            )

        completeness_and_accuracy = PopulationCompletenessAccuracy.objects.get(
            id=completeness_accuracy_id,
            population_id=population_id,
            population__audit_id=audit_id,
        )
        completeness_and_accuracy.update_name(new_name)

        return UpdateAuditorPopulationCompletenessAndAccuracy(
            completeness_accuracy=completeness_and_accuracy
        )


class DeleteAuditorPopulationCompletenessAccuracy(graphene.Mutation):
    class Arguments:
        input = DeletePopulationCompletenessAccuracyInput(required=True)

    completeness_accuracy = graphene.Field(PopulationCompletenessAccuracyType)

    @audit_service(
        permission='population.delete_populationcompletenessaccuracy',
        exception_msg='Failed to delete completeness accuracy file',
        revision_name='Delete audit population completeness accuracy file',
    )
    def mutate(self, info, input):
        completeness_accuracy_id = input.id
        audit_id = input.audit_id
        population_id = input.population_id
        user = info.context.user

        audit = Audit.objects.get(id=audit_id)
        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException(
                'Auditor can not delete completeness and accuracy file'
            )

        completeness_accuracy = PopulationCompletenessAccuracy.objects.get(
            id=completeness_accuracy_id,
            population_id=population_id,
            population__audit_id=audit_id,
        )
        completeness_accuracy.is_deleted = True
        completeness_accuracy.save()

        return DeleteAuditorPopulationCompletenessAccuracy(
            completeness_accuracy=completeness_accuracy
        )


class CreateAuditorPopulationSample(graphene.Mutation):
    class Arguments:
        input = CreateAuditorPopulationSampleInput(required=True)

    population_data = graphene.List(PopulationDataType)

    @audit_service(
        permission='population.change_auditpopulation',
        exception_msg='Failed to create population sample ',
        revision_name='Create population sample',
    )
    def mutate(self, info, input):
        audit_id = input.get('audit_id')
        population_id = input.get('population_id')
        user = info.context.user
        sample_size = input.get('sample_size')
        population_data_ids = input.get('population_data_ids')

        audit = Audit.objects.get(id=audit_id)
        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException('Auditor can not update population')

        population = AuditPopulation.objects.get(audit__id=audit.id, id=population_id)

        population_data_count = PopulationData.objects.filter(
            population__id=population.id
        ).count()

        if sample_size <= 0 or sample_size > population_data_count:
            raise ServiceException(f'Invalid sample size population {population.id}')

        PopulationData.remove_sample(population_id)

        selected_population_data = PopulationData.objects.filter(
            id__in=population_data_ids, population__id=population.id
        )

        selected_items = len(selected_population_data)
        random_items = sample_size - selected_items
        if selected_items > sample_size:
            sample_size = selected_items
            random_items = 0

        population.sample_size = sample_size
        population.save()

        population_filters = population.get_query_filters()

        random_population_data = (
            PopulationData.objects.filter(population__id=population.id)
            .filter(population_filters)
            .exclude(id__in=population_data_ids)
            .order_by('?')[:random_items]
        )

        population_data = random_population_data | selected_population_data
        for data in population_data:
            data.is_sample = True
        PopulationData.objects.bulk_update(population_data, ['is_sample'])

        return CreateAuditorPopulationSample(population_data=population_data)


class CreateAuditorSampleSize(graphene.Mutation):
    class Arguments:
        input = PopulationInput(required=True)

    population = graphene.Field(AuditPopulationType)

    @audit_service(
        permission='population.change_auditpopulation',
        exception_msg='Failed to update sample size',
        revision_name='Update population sample size',
    )
    def mutate(self, info, input):
        audit_id = input.get('audit_id')
        population_id = input.get('population_id')
        user = info.context.user

        audit = Audit.objects.get(id=audit_id)
        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException("Auditor can not update population")

        population = AuditPopulation.objects.get(audit__id=audit.id, id=population_id)

        population_filters = population.get_query_filters()

        population_data = PopulationData.objects.filter(
            population__id=population.id
        ).filter(population_filters)

        population_count = population_data.count()
        sample_size = math.floor(population_count * 0.25)

        population.sample_size = sample_size if sample_size > 0 else 1
        population.save()

        return CreateAuditorSampleSize(population=population)


class DeleteAuditorPopulationSample(graphene.Mutation):
    class Arguments:
        input = DeleteAuditorAuditPopulationInput(required=True)

    samples = graphene.List(PopulationDataType)

    @audit_service(
        permission='population.delete_auditpopulation',
        exception_msg='Failed to delete population sample ',
        revision_name='Delete population sample',
    )
    def mutate(self, info, input):
        audit_id = input.get('audit_id')
        population_id = input.get('population_id')
        sample_ids = input.get('sample_ids')
        user = info.context.user

        audit = Audit.objects.get(id=audit_id)
        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException('Auditor can not delete population sample')

        population = AuditPopulation.objects.get(audit__id=audit_id, id=population_id)
        filters = {
            'population__id': population.id,
            'id__in': sample_ids,
            'is_sample': True,
        }
        samples = PopulationData.objects.filter(**filters)
        for data in samples:
            data.is_sample = False

        PopulationData.objects.bulk_update(samples, ['is_sample'])

        return DeleteAuditorPopulationSample(samples=samples)


class AddAuditorPopulationSample(graphene.Mutation):
    class Arguments:
        input = PopulationInput(required=True)

    sample = graphene.Field(PopulationDataType)

    @audit_service(
        permission='population.change_auditpopulation',
        exception_msg='Failed to add another population sample',
        revision_name='Adding another population sample',
    )
    def mutate(self, info, input):
        audit_id = input.get('audit_id')
        population_id = input.get('population_id')
        user = info.context.user

        audit = Audit.objects.get(id=audit_id)
        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException('Auditor can not add items to population sample')

        population = AuditPopulation.objects.get(audit__id=audit.id, id=population_id)

        population_filters = population.get_query_filters()

        population_data = (
            PopulationData.objects.filter(population__id=population.id)
            .filter(population_filters)
            .filter(is_sample=False)
            .order_by('?')
            .first()
        )

        if not population_data:
            raise ServiceException('There are no more available items to add')

        population_data.is_sample = True
        population_data.save(update_fields=['is_sample'])

        return AddAuditorPopulationSample(sample=population_data)


class AttachSampleToEvidenceRequest(graphene.Mutation):
    class Arguments:
        input = PopulationInput(required=True)

    evidence_request = graphene.List(FieldworkEvidenceType)

    @audit_service(
        permission='population.change_auditpopulation',
        exception_msg='Error attaching sample to evidence request',
        revision_name='Attach sample to evidence request',
    )
    def mutate(self, info, input):
        audit_id = input.get('audit_id')
        population_id = input.get('population_id')
        user = info.context.user

        audit = Audit.objects.get(id=audit_id)
        if not is_auditor_associated_to_audit_firm(audit=audit, auditor_id=user.id):
            raise ServiceException('Auditor can not attach sample to evidence requests')

        population = AuditPopulation.objects.get(audit__id=audit.id, id=population_id)

        population_data = PopulationData.objects.filter(
            population__id=population.id, is_sample=True
        )

        evidence_request = population.evidence_request.filter(
            is_deleted=False, er_type=dict(ER_TYPE)['sample_er']
        )

        for er in evidence_request:
            er.population_sample.add(*population_data)
            samples = Sample.objects.filter(evidence_request=er)
            for sample in samples:
                set_sample_name(sample)

        return AttachSampleToEvidenceRequest(evidence_request=evidence_request)


class PopulationMutation(object):
    update_auditor_audit_population = UpdateAuditorAuditPopulation.Field()

    update_auditor_population_completeness_accuracy = (
        UpdateAuditorPopulationCompletenessAndAccuracy.Field()
    )
    delete_auditor_population_completeness_accuracy = (
        DeleteAuditorPopulationCompletenessAccuracy.Field()
    )

    create_auditor_population_sample = CreateAuditorPopulationSample.Field()

    create_auditor_sample_size = CreateAuditorSampleSize.Field()

    delete_auditor_population_sample = DeleteAuditorPopulationSample.Field()
    add_auditor_population_sample = AddAuditorPopulationSample.Field()
    attach_sample_to_evidence_request = AttachSampleToEvidenceRequest.Field()
