from dataclasses import asdict, dataclass, field

from organization.models import Organization
from tag.models import Tag
from user.models import User


@dataclass()
class Filter:
    types: dict = field(compare=False, default_factory=dict)
    owners: dict = field(compare=False, default_factory=dict)
    tags: dict = field(compare=False, default_factory=dict)

    def export(self):
        return [attr for attr in asdict(self).values()]


class FilterBuilder:
    filter = Filter()

    def __init__(self, organization: Organization):
        self.organization = organization

    def add_types(self):
        evidence_types = self.organization.drive.evidence.values(
            'evidence__type'
        ).distinct()
        types = [
            {
                'id': _type['evidence__type'],
                'name': _type['evidence__type'].title().replace('_', ' '),
            }
            for _type in list(evidence_types)
        ]
        self.filter.types = {'id': 'type', 'category': 'Type', 'items': types}

    def add_owners(self):
        drive_evidence = self.organization.drive.evidence.all()
        users = User.objects.filter(
            organization=self.organization, owned_evidence__in=drive_evidence
        ).distinct()
        owners = [
            {
                'name': user.get_full_name(),
                'id': user.id,
            }
            for user in users
        ]

        self.filter.owners = {
            'id': 'owner',
            'category': 'Owner',
            'items': owners,
        }

    def add_tags(self):
        drive = self.organization.drive
        tags = (
            Tag.objects.filter(
                organization=self.organization,
                tagevidence__evidence__drive__drive=drive,
            )
            .order_by('name')
            .distinct()
            .values('name', 'id')
        )

        self.filter.tags = {'id': 'tags', 'category': 'Tags', 'items': tags}
