from abc import ABC, abstractmethod

from population.constants import (
    POP_1,
    POP_2,
    POPULATION_DEFAULT_SOURCE_DICT,
    POPULATION_DISPLAY_IDS,
)
from population.models import AuditPopulation
from population.population_builder.schemas import POPULATION_LAIKA_SOURCE_SCHEMAS
from user.models import User


class PopulationGenerator(ABC):
    def __init__(self, population: AuditPopulation):
        self.population = population

    @abstractmethod
    def laika_source_data_exists(self) -> bool:
        pass

    @abstractmethod
    def generate_population_rows(self):
        pass

    def _validate_row(self, row):
        schema = POPULATION_LAIKA_SOURCE_SCHEMAS.get(self.population.display_id)
        errors = []
        for field in schema.fields:
            value = row[field.name] if field.name in row else None
            error = field.validate(value)
            if error:
                errors.append(error)
        return errors

    def _format_row(self, schema, row):
        formatted_row = {}
        for field in schema.fields:
            formatted_row[field.name] = field.format(row[field.name])
        return formatted_row


class PeoplePopulationGenerator(PopulationGenerator):
    def _get_user_data(self):
        users = self.population.audit.organization.get_users(exclude_super_admin=True)

        if self.population.display_id == POP_1:
            return users.exclude(end_date__isnull=False)
        if self.population.display_id == POP_2:
            return users.filter(end_date__isnull=False)

    def laika_source_data_exists(self) -> bool:
        rows, errors = self.generate_population_rows()
        if errors:
            return False

        return True if rows else False

    def generate_population_rows(self):
        schema = POPULATION_LAIKA_SOURCE_SCHEMAS.get(self.population.display_id)
        users = self._get_user_data()
        rows = [self._build_row(user) for user in users]
        errors = []
        formatted_rows = []
        for row in rows:
            error = self._validate_row(row)
            if error:
                errors.append(error)
            else:
                formatted_rows.append(self._format_row(schema, row))
        return formatted_rows, errors

    def _build_row(self, user: User):
        base_row = {
            "Name": f'{user.first_name} {user.last_name}',
            "Email": user.email,
            "Title": user.title,
            "Employment Type": user.employment_type,
        }
        if self.population.display_id == POPULATION_DISPLAY_IDS['POP-1']:
            return {**base_row, "Start Date": user.start_date}
        elif self.population.display_id == POPULATION_DISPLAY_IDS['POP-2']:
            return {**base_row, "End Date": user.end_date}


def get_population_generator(default_source: str):
    population_generators = {
        POPULATION_DEFAULT_SOURCE_DICT['People']: PeoplePopulationGenerator
    }
    return population_generators.get(default_source)
