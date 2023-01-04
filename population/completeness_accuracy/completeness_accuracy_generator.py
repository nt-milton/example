import io
from abc import ABC, abstractmethod

from django.core.files import File

from fieldwork.constants import ACCOUNT_OBJECT_TYPE
from laika.utils.spreadsheet import save_virtual_workbook
from objects.models import LaikaObjectType
from objects.views import write_export_response
from population.constants import POP_1, POP_2, POPULATION_DEFAULT_SOURCE_DICT
from population.models import AuditPopulation, PopulationCompletenessAccuracy

COMPLETENESS_ACCURACY_FILE_NAMES = {POP_1: 'Population 1', POP_2: 'Population 2'}

COMPLETENESS_ACCURACY_TITLES = {POP_1: 'Users', POP_2: 'Users'}

INITIAL_USER_ROW = 3


class CompletenessAccuracyFileGenerator(ABC):
    def __init__(self, population: AuditPopulation):
        self.population = population

    @abstractmethod
    def create_population_completeness_accuracy(self):
        pass

    @abstractmethod
    def _generate_file(self):
        pass

    def _get_file_name(self):
        return f'Completeness and Accuracy - {self.population.display_id}.xlsx'


class PeopleCompletenessAccuracyFileGenerator(CompletenessAccuracyFileGenerator):
    def create_population_completeness_accuracy(self):
        file = self._generate_file()
        file_name = self._get_file_name()
        return PopulationCompletenessAccuracy.objects.create(
            name=file_name,
            population=self.population,
            file=File(name=f'{file_name}.xlsx', file=io.BytesIO(file)),
        )

    def _generate_file(self):
        organization = self.population.audit.organization
        accounts_object_type = LaikaObjectType.objects.filter(
            organization=organization,
            type_name=ACCOUNT_OBJECT_TYPE,
        ).first()

        workbook = write_export_response(
            accounts_object_type.id,
            [accounts_object_type],
        )
        file = save_virtual_workbook(workbook)
        return file


class CompletenessAccuracyGeneratorFactory:
    @staticmethod
    def get_completeness_accuracy_generator(default_source, audit_population):
        completeness_accuracy_generator = {
            POPULATION_DEFAULT_SOURCE_DICT[
                'People'
            ]: PeopleCompletenessAccuracyFileGenerator
        }

        generator = completeness_accuracy_generator.get(default_source)

        return generator(audit_population)
