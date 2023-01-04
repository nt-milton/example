from dataclasses import asdict, dataclass, field

from django.db.models.query_utils import Q

from certification.models import UnlockedOrganizationCertification
from control.constants import CONTROLS_HEALTH_FILTERS, STATUS
from control.models import ControlPillar
from laika.utils.filter_builder import ControlFilterBuilder
from tag.models import Tag
from user.models import User


@dataclass()
class Filter:
    owners: dict = field(compare=False, default_factory=dict)
    status: dict = field(compare=False, default_factory=dict)
    health: dict = field(compare=False, default_factory=dict)
    frameworks: dict = field(compare=False, default_factory=dict)
    pillars: dict = field(compare=False, default_factory=dict)
    tags: dict = field(compare=False, default_factory=dict)


class FilterBuilder(ControlFilterBuilder):
    control_filter = Filter()

    def add_status(self, organization_id):
        self.control_filter.status = {
            'id': 'status',
            'category': 'STATUS',
            'items': [
                {
                    'id': STATUS.get('IMPLEMENTED'),
                    'name': STATUS.get('IMPLEMENTED').title(),
                },
                {
                    'id': STATUS.get('NOT IMPLEMENTED'),
                    'name': STATUS.get('NOT IMPLEMENTED').title(),
                },
            ],
        }

    def add_health(self, organization_id):
        self.control_filter.health = {
            'id': 'health',
            'category': 'HEALTH',
            'items': [
                {
                    'id': CONTROLS_HEALTH_FILTERS.get('NEEDS_ATTENTION'),
                    'name': CONTROLS_HEALTH_FILTERS.get('NEEDS_ATTENTION')
                    .title()
                    .replace('_', ' '),
                },
                {
                    'id': CONTROLS_HEALTH_FILTERS.get('OPERATIONAL'),
                    'name': CONTROLS_HEALTH_FILTERS.get('OPERATIONAL').title(),
                },
            ],
        }

    def add_frameworks(self, organization_id):
        certifications = (
            UnlockedOrganizationCertification.objects.filter(
                organization_id=organization_id
            )
            .distinct()
            .order_by('certification__name')
        )
        self.control_filter.frameworks = {
            'id': 'framework',
            'category': 'FRAMEWORK',
            'items': [
                {'id': c.certification.id, 'name': c.certification.name}
                for c in certifications
            ],
        }

    def add_pillars(self, organization_id):
        pillars = (
            ControlPillar.objects.filter(control__organization_id=organization_id)
            .distinct()
            .order_by('name')
        )
        self.control_filter.pillars = {
            'id': 'pillar',
            'category': 'CONTROL FAMILY',
            'items': [{'id': p.id, 'name': p.full_name} for p in pillars],
        }

    def add_tags(self, organization_id):
        tags = (
            Tag.objects.filter(controls__organization_id=organization_id)
            .distinct()
            .order_by('name')
        )
        self.control_filter.tags = {
            'id': 'tag',
            'category': 'TAGS',
            'items': [{'id': t.id, 'name': t.name} for t in tags],
        }

    def add_owners(self, organization_id):
        users = (
            User.objects.filter(
                (
                    Q(control_owner__isnull=False)
                    | Q(control_owner1__isnull=False)
                    | Q(control_owner2__isnull=False)
                ),
                organization_id=organization_id,
            )
            .distinct()
            .order_by('first_name')
        )

        self.control_filter.owners = {
            'id': 'owners',
            'category': 'OWNERS',
            'items': [
                {
                    'id': u.id,
                    'name': u.get_full_name().title(),
                    'firstName': u.first_name.title(),
                    'lastName': u.last_name.title(),
                }
                for u in users
            ],
        }

    def export(self):
        return [attr for attr in asdict(self.control_filter).values() if attr]
