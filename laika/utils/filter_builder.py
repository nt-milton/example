from abc import ABC, abstractmethod
from typing import Tuple


class FilterBuilder(ABC):
    @abstractmethod
    def add_tags(self, organization_id, **kwargs):
        pass

    @abstractmethod
    def add_owners(self, organization_id, **kwargs):
        pass

    @abstractmethod
    def export(self):
        pass


class ControlFilterBuilder(FilterBuilder):
    @abstractmethod
    def add_status(self, organization_id, **kwargs):
        pass

    @abstractmethod
    def add_health(self, organization_id, **kwargs):
        pass

    @abstractmethod
    def add_frameworks(self, organization_id, **kwargs):
        pass

    @abstractmethod
    def add_pillars(self, organization_id, **kwargs):
        pass


class PolicyFilterBuilder(FilterBuilder):
    @abstractmethod
    def add_status(self, organization_id, **kwargs):
        pass

    @abstractmethod
    def add_type(self, organization_id, **kwargs):
        pass

    @abstractmethod
    def add_category(self, organization_id, **kwargs):
        pass


def get_available_choice_from_tuple(tuple_choice: Tuple[Tuple[str, str]]):
    return [{'id': choice[0], 'name': choice[1]} for choice in tuple_choice]
