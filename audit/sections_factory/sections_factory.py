import io
from abc import ABC, abstractmethod
from typing import Union

from django.core.files import File
from django.template import Context, Template

from audit.constants import SECTION_1, SECTION_2, SECTION_3, SECTION_4, SECTION_5
from audit.models import Audit


class Section(ABC):
    def __init__(self, audit: Audit):
        self.audit = audit
        self.section = ''

    def create_section_file(self):
        template_file: File = self.audit.audit_framework_type.templates.filter(
            section=self.section
        ).first()
        context = self._generate_context()

        if context is None or template_file is None:
            return

        template = Template(template_file.file.read().decode('utf-8'))
        template_content = template.render(Context(context))
        generated_section_file = File(
            name=f'{self.section}.html', file=io.BytesIO(template_content.encode())
        )
        return {
            'file': generated_section_file,
            'section': self.section,
            'name': template_file.name,
        }

    @abstractmethod
    def _generate_context(self):
        pass


class Section1(Section):
    def __init__(self, audit: Audit):
        super().__init__(audit=audit)
        self.section = SECTION_1

    @abstractmethod
    def _generate_context(self):
        pass


class Section2(Section):
    def __init__(self, audit: Audit):
        super().__init__(audit=audit)
        self.section = SECTION_2

    @abstractmethod
    def _generate_context(self):
        pass


class Section3(Section):
    def __init__(self, audit: Audit):
        super().__init__(audit=audit)
        self.section = SECTION_3

    @abstractmethod
    def _generate_context(self):
        pass


class Section4(Section):
    def __init__(self, audit: Audit):
        super().__init__(audit=audit)
        self.section = SECTION_4

    @abstractmethod
    def _generate_context(self):
        pass


class Section5(Section):
    def __init__(self, audit: Audit):
        super().__init__(audit=audit)
        self.section = SECTION_5

    @abstractmethod
    def _generate_context(self):
        pass


class SectionsFactory(ABC):
    def __init__(self, audit: Audit):
        self.audit = audit

    @abstractmethod
    def create_section_1(self) -> Union[dict, None]:
        pass

    @abstractmethod
    def create_section_2(self) -> Union[dict, None]:
        pass

    @abstractmethod
    def create_section_3(self) -> Union[dict, None]:
        pass

    @abstractmethod
    def create_section_4(self) -> Union[dict, None]:
        pass

    @abstractmethod
    def create_section_5(self) -> Union[dict, None]:
        pass
