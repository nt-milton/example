from dataclasses import asdict, dataclass, field

from django.db.models import F

from laika.utils.filter_builder import PolicyFilterBuilder
from policy.models import Policy
from policy.types import PolicyTypes
from tag.models import Tag
from user.models import User


@dataclass()
class Filter:
    owners: dict = field(compare=False, default_factory=dict)
    type: dict = field(compare=False, default_factory=dict)
    category: dict = field(compare=False, default_factory=dict)
    status: dict = field(compare=False, default_factory=dict)
    tags: dict = field(compare=False, default_factory=dict)


class FilterBuilder(PolicyFilterBuilder):
    policy_filter = Filter()

    def add_status(self, organization_id):
        self.policy_filter.status = {
            'id': 'isPublished',
            'category': 'Published Status',
            'items': [
                {
                    'id': 'published',
                    'name': 'Published',
                },
                {
                    'id': 'not_published',
                    'name': 'Not Published',
                },
            ],
        }

    def add_category(self, organization_id, display_control_family_filter_name):
        categories = [
            {'id': item['category'], 'name': item['category']}
            for item in Policy.objects.filter(organization_id=organization_id)
            .order_by('category')
            .values('category')
            .distinct()
        ]

        control_families = [
            {'id': item['control_family'], 'name': item['control_family_name']}
            for item in Policy.objects.filter(organization_id=organization_id)
            .order_by('control_family__name')
            .exclude(control_family__isnull=True)
            .values('control_family', control_family_name=F('control_family__name'))
            .distinct()
        ]

        control_family_or_category = (
            {
                'id': 'controlFamily',
                'category': 'Control Family',
                'items': [*control_families],
            }
            if display_control_family_filter_name
            else {'id': 'category', 'category': 'Category', 'items': [*categories]}
        )

        self.policy_filter.category = control_family_or_category

    def add_tags(self, organization_id, organization):
        tags = (
            Tag.objects.filter(policies__in=organization.policies.all())
            .order_by('name')
            .distinct()
            .values('name', 'id')
        )

        self.policy_filter.tags = {'id': 'tags', 'category': 'Tags', 'items': tags}

    def add_owners(self, organization_id):
        users = User.objects.filter(
            policy_owned__isnull=False, organization_id=organization_id
        ).distinct()
        owners = [
            {
                'name': user.get_full_name(),
                'id': user.id,
            }
            for user in users
        ]

        self.policy_filter.owners = {
            'id': 'owner',
            'category': 'Owner',
            'items': owners,
        }

    def add_type(self, organization_id):
        self.policy_filter.type = {
            'id': 'type',
            'category': 'Type',
            'items': [
                {
                    'id': PolicyTypes.POLICY.value,
                    'name': PolicyTypes.POLICY.value,
                },
                {
                    'id': PolicyTypes.PROCEDURE.value,
                    'name': PolicyTypes.PROCEDURE.value,
                },
            ],
        }

    def export(self):
        return [attr for attr in asdict(self.policy_filter).values() if attr]
