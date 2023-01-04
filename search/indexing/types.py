import dataclasses
from typing import List


@dataclasses.dataclass
class RecordFields:
    type: str
    organization_id: str
    title: str
    main_content: str
    secondary_content: str
    category: List[str]
    is_draft: int


@dataclasses.dataclass
class IndexRecord:
    id: str
    fields: RecordFields

    def __init__(
        self,
        resource_id,
        resource_type,
        organization_id,
        title,
        main_content,
        secondary_content,
        category,
        is_draft: bool,
    ):
        self.id = f'{resource_type}-{resource_id}'
        self.fields = RecordFields(
            resource_type,
            organization_id=str(organization_id),
            title=title,
            main_content=main_content or '',
            secondary_content=secondary_content or '',
            category=category or [],
            is_draft=int(is_draft),
        )

    @property
    def resource_id(self):
        delimiter = '-'
        return delimiter.join(self.id.split(delimiter)[1:])
