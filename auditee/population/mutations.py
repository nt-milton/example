import base64
import io

import graphene
from django.core.files import File

from evidence.evidence_handler import get_files_to_upload
from fieldwork.inputs import (
    AddPopulationCompletenessAccuracyInput,
    DeletePopulationCompletenessAccuracyInput,
    DeletePopulationDataFileInput,
    UpdatePopulationCompletenessAccuracyInput,
    UpdatePopulationInput,
    UploadPopulationFileInput,
)
from laika.decorators import laika_service
from laika.types import DataFileType
from laika.utils.exceptions import ServiceException
from laika.utils.files import filename_has_extension
from laika.utils.increment_file_name import increment_file_name
from laika.utils.schema_builder.template_builder import TemplateBuilder
from population.completeness_accuracy.completeness_accuracy_generator import (
    CompletenessAccuracyGeneratorFactory,
)
from population.constants import (
    COMPLETENESS_AND_ACCURACY_MAX_FILES_AMOUNT,
    POPULATION_SOURCE_DICT,
    ZIP_FILE_EXTENSION,
)
from population.inputs import LaikaSourcePopulationInput, PopulationInput
from population.models import (
    AuditPopulation,
    PopulationCompletenessAccuracy,
    PopulationData,
)
from population.population_builder.population_generator import get_population_generator
from population.population_builder.schemas import POPULATION_SCHEMAS
from population.types import (
    AuditPopulationType,
    LaikaSourcePopulationResponseType,
    ManualSourcePopulationResponseType,
    PopulationBulkUploadType,
    PopulationCompletenessAccuracyType,
)
from population.utils import reset_population_data


class UpdateAuditeePopulation(graphene.Mutation):
    class Arguments:
        input = UpdatePopulationInput(required=True)

    audit_population = graphene.Field(AuditPopulationType)

    @laika_service(
        permission='population.change_auditpopulation',
        exception_msg='Failed to update audit population',
        revision_name='Update audit population',
    )
    def mutate(self, info, input):
        audit_population = AuditPopulation.objects.get(
            audit__id=input.audit_id, id=input.population_id
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
        return UpdateAuditeePopulation(audit_population=audit_population)


class DeleteAuditeePopulationDataFile(graphene.Mutation):
    class Arguments:
        input = DeletePopulationDataFileInput(required=True)

    audit_population = graphene.Field(AuditPopulationType)

    @laika_service(
        permission='population.change_auditpopulation',
        exception_msg='Failed to delete audit population data file',
        revision_name='Delete audit population data file',
    )
    def mutate(self, info, input):
        audit_population = AuditPopulation.objects.get(
            audit__id=input.audit_id, id=input.population_id
        )
        if audit_population.data_file:
            audit_population.data_file.delete()
        audit_population.data_file_name = ''
        audit_population.save()

        return DeleteAuditeePopulationDataFile(audit_population=audit_population)


class AddAuditeePopulationCompletenessAccuracy(graphene.Mutation):
    class Arguments:
        input = AddPopulationCompletenessAccuracyInput(required=True)

    completeness_accuracy_list = graphene.List(PopulationCompletenessAccuracyType)

    @laika_service(
        permission='population.add_populationcompletenessaccuracy',
        exception_msg='Failed to add completeness accuracy',
        revision_name='Add audit population completeness accuracy',
    )
    def mutate(self, info, input):
        population_id = input.population_id
        audit_population = AuditPopulation.objects.get(
            id=population_id, audit__id=input.audit_id
        )

        new_files = input.files

        filters = {'population': audit_population, 'is_deleted': False}
        current_files = PopulationCompletenessAccuracy.objects.filter(**filters)

        is_max_number_filed_exceeded = (
            len(new_files) + current_files.count()
            > COMPLETENESS_AND_ACCURACY_MAX_FILES_AMOUNT
        )

        if is_max_number_filed_exceeded:
            raise ServiceException('Max number of files exceeded')

        if len(new_files) == 0:
            raise ServiceException('No files found')

        files_to_upload = get_files_to_upload(new_files)

        completeness_accuracy_list = []
        for file in files_to_upload:
            if filename_has_extension(file.name, ZIP_FILE_EXTENSION):
                raise ServiceException('File type not supported')

            file_name = increment_file_name(
                filters=filters,
                reference_model=PopulationCompletenessAccuracy,
                file_name=file.name,
            )

            completeness_accuracy_list.append(
                PopulationCompletenessAccuracy(
                    population=audit_population, name=file_name, file=file
                )
            )
        completeness_accuracies = PopulationCompletenessAccuracy.objects.bulk_create(
            completeness_accuracy_list
        )
        return AddAuditeePopulationCompletenessAccuracy(
            completeness_accuracy_list=completeness_accuracies
        )


class UpdateAuditeePopulationCompletenessAndAccuracy(graphene.Mutation):
    class Arguments:
        input = UpdatePopulationCompletenessAccuracyInput(required=True)

    completeness_accuracy = graphene.Field(PopulationCompletenessAccuracyType)

    @laika_service(
        permission='population.change_populationcompletenessaccuracy',
        exception_msg='Failed to update completeness accuracy',
        revision_name='Update population completeness accuracy',
    )
    def mutate(self, info, input):
        completeness_accuracy_id = input.id
        audit_id = input.audit_id
        population_id = input.population_id
        new_name = input.new_name

        completeness_and_accuracy = PopulationCompletenessAccuracy.objects.get(
            id=completeness_accuracy_id,
            population_id=population_id,
            population__audit_id=audit_id,
        )
        completeness_and_accuracy.update_name(new_name)

        return UpdateAuditeePopulationCompletenessAndAccuracy(
            completeness_accuracy=completeness_and_accuracy
        )


class DeleteAuditeePopulationCompletenessAccuracy(graphene.Mutation):
    class Arguments:
        input = DeletePopulationCompletenessAccuracyInput(required=True)

    completeness_accuracy = graphene.Field(PopulationCompletenessAccuracyType)

    @laika_service(
        permission='population.delete_populationcompletenessaccuracy',
        exception_msg='Failed to delete completeness accuracy file',
        revision_name='Delete audit population completeness accuracy file',
    )
    def mutate(self, info, input):
        completeness_accuracy_id = input.id
        audit_id = input.audit_id
        population_id = input.population_id

        completeness_accuracy = PopulationCompletenessAccuracy.objects.get(
            id=completeness_accuracy_id,
            population_id=population_id,
            population__audit_id=audit_id,
        )
        completeness_accuracy.is_deleted = True
        completeness_accuracy.save()

        return DeleteAuditeePopulationCompletenessAccuracy(
            completeness_accuracy=completeness_accuracy
        )


class UploadAuditeePopulationFile(graphene.Mutation):
    class Arguments:
        input = UploadPopulationFileInput(required=True)

    upload_result = graphene.Field(PopulationBulkUploadType)

    @laika_service(
        permission='population.change_auditpopulation',
        exception_msg='Failed to upload population file',
        revision_name='Upload population file',
    )
    def mutate(self, info, input):
        audit_population = AuditPopulation.objects.get(
            audit__id=input.audit_id, id=input.population_id
        )

        population_schema = POPULATION_SCHEMAS[audit_population.display_id]

        builder = TemplateBuilder(schemas=[population_schema])
        data = builder.parse(input.data_file)
        results = data[population_schema.sheet_name]

        if results.error:
            error_message = str(results.error)
            error_to_raise = results.error
            if 'Missing sheet' in error_message:
                error_to_raise = ServiceException(
                    'Incorrect file. This population only accepts the '
                    f'template for {population_schema.sheet_name}.'
                )
            elif 'Missing header' in error_message:
                missing_column = error_message.replace('Missing header ', '')
                error_to_raise = ServiceException(
                    'File is missing the section '
                    f'for {missing_column}. See template in instructions.'
                )

            raise error_to_raise

        if len(results.failed_rows) == 0 and len(results.success_rows) == 0:
            raise ServiceException("File can't be uploaded because it is empty.")

        if results.failed_rows:
            return UploadAuditeePopulationFile(
                upload_result=PopulationBulkUploadType(
                    failed_rows=builder.summarize_errors(results.failed_rows),
                    success=False,
                )
            )

        data_file_name = input.data_file.file_name
        audit_population.data_file_name = data_file_name
        audit_population.data_file = File(
            name=data_file_name, file=io.BytesIO(base64.b64decode(input.data_file.file))
        )

        audit_population.save()

        return UploadAuditeePopulationFile(
            upload_result=PopulationBulkUploadType(
                success=True, audit_population=audit_population
            )
        )


class CreateAuditeeLaikaSourcePopulation(graphene.Mutation):
    class Arguments:
        input = LaikaSourcePopulationInput(required=True)

    laika_source_population = graphene.Field(LaikaSourcePopulationResponseType)

    @laika_service(
        permission='population.add_auditpopulation',
        exception_msg='Failed to create population from laika source',
        revision_name='Create population from laika source',
    )
    def mutate(self, info, input):
        audit_population = AuditPopulation.objects.get(
            id=input.get('population_id'), audit__id=input.get('audit_id')
        )
        source = input.get('source')
        population_generator = get_population_generator(source)

        reset_population_data(audit_population, POPULATION_SOURCE_DICT['laika_source'])
        rows, errors = population_generator(audit_population).generate_population_rows()

        if errors:
            return CreateAuditeeLaikaSourcePopulation(
                laika_source_population=LaikaSourcePopulationResponseType(
                    population_data=[], errors=True
                )
            )
        population_data = [
            PopulationData(population=audit_population, data=row) for row in rows
        ]

        created_population = PopulationData.objects.bulk_create(population_data)

        audit_population.selected_source = POPULATION_SOURCE_DICT['laika_source']
        audit_population.selected_default_source = source
        audit_population.save()

        return CreateAuditeeLaikaSourcePopulation(
            laika_source_population=LaikaSourcePopulationResponseType(
                population_data=created_population, errors=False
            )
        )


class CreateAuditeeManualSourcePopulation(graphene.Mutation):
    class Arguments:
        input = PopulationInput(required=True)

    manual_source_population = graphene.Field(ManualSourcePopulationResponseType)

    @laika_service(
        permission='population.change_auditpopulation',
        exception_msg='Failed to create population from manual source',
        revision_name='Create population from manual source',
    )
    def mutate(self, info, input):
        audit_population = AuditPopulation.objects.get(
            id=input.get('population_id'), audit__id=input.get('audit_id')
        )

        reset_population_data(audit_population, POPULATION_SOURCE_DICT['manual'])

        population_schema = POPULATION_SCHEMAS[audit_population.display_id]
        file_data = DataFileType(
            file_name=audit_population.data_file_name,
            file=base64.b64encode(audit_population.data_file.file.read()).decode(
                'UTF-8'
            ),
        )

        builder = TemplateBuilder(schemas=[population_schema])
        data = builder.parse(file_data)
        results = data[population_schema.sheet_name]

        success_rows = results.success_rows
        population_data = [
            PopulationData(population=audit_population, data=data)
            for data in success_rows
        ]
        created_population = PopulationData.objects.bulk_create(population_data)

        audit_population.selected_source = POPULATION_SOURCE_DICT['manual']
        audit_population.save()

        return CreateAuditeeManualSourcePopulation(
            manual_source_population=ManualSourcePopulationResponseType(
                population_data=created_population
            )
        )


class CreateAuditeeLaikaSourceCompletenessAccuracy(graphene.Mutation):
    class Arguments:
        input = LaikaSourcePopulationInput(required=True)

    population_completeness_accuracy = graphene.Field(
        PopulationCompletenessAccuracyType
    )

    @laika_service(
        permission='population.add_populationcompletenessaccuracy',
        exception_msg='Failed to create laika source completeness and accuracy',
        revision_name='Create laika source completeness and accuracy',
    )
    def mutate(self, info, input):
        audit_population = AuditPopulation.objects.get(
            id=input.get('population_id'), audit__id=input.get('audit_id')
        )
        source = input.get('source')

        completeness_accuracy_generator = (
            CompletenessAccuracyGeneratorFactory.get_completeness_accuracy_generator(
                source, audit_population
            )
        )

        population_completeness_accuracy = (
            completeness_accuracy_generator.create_population_completeness_accuracy()
        )

        return CreateAuditeeLaikaSourceCompletenessAccuracy(
            population_completeness_accuracy=population_completeness_accuracy
        )


class PopulationMutation(object):
    update_auditee_population = UpdateAuditeePopulation.Field()
    delete_auditee_population_data_file = DeleteAuditeePopulationDataFile.Field()
    add_auditee_population_completeness_accuracy = (
        AddAuditeePopulationCompletenessAccuracy.Field()
    )
    update_auditee_population_completeness_accuracy = (
        UpdateAuditeePopulationCompletenessAndAccuracy.Field()
    )
    delete_auditee_population_completeness_accuracy = (
        DeleteAuditeePopulationCompletenessAccuracy.Field()
    )
    upload_auditee_population_file = UploadAuditeePopulationFile.Field()

    create_auditee_laika_source_population = CreateAuditeeLaikaSourcePopulation.Field()
    create_auditee_manual_source_population = (
        CreateAuditeeManualSourcePopulation.Field()
    )

    create_auditee_laika_source_completeness_accuracy = (
        CreateAuditeeLaikaSourceCompletenessAccuracy.Field()
    )
