from abc import ABC, abstractmethod
from dataclasses import dataclass

from control.helpers import get_health_stats
from control.models import Control
from integration.constants import ERROR
from integration.models import ConnectionAccount
from monitor.helpers import get_monitors_status_stats
from monitor.models import OrganizationMonitor
from policy.models import Policy


@dataclass
class QuickLink:
    id: str
    name: str
    total: int
    data_number: int


class QuickLinkBase(ABC):
    @abstractmethod
    def get_quick_link(self):
        pass


class ControlQuickLink(QuickLinkBase):
    def get_quick_link(self, organization_id):
        organization_controls = Control.objects.filter(organization_id=organization_id)
        total_controls = organization_controls.count()

        controls_health = Control.controls_health(organization_id)

        health_stats = get_health_stats(controls_health)

        return QuickLink(
            id='control',
            name='Controls',
            total=total_controls,
            data_number=health_stats.get('flagged', 0),
        )


class PolicyQuickLink(QuickLinkBase):
    def get_quick_link(self, organization_id):
        organization_policies = Policy.objects.filter(organization_id=organization_id)
        total_policies = organization_policies.count()
        unpublished_policies = organization_policies.filter(is_published=False)

        return QuickLink(
            id='policy',
            name='Policies & Procedures',
            total=total_policies,
            data_number=unpublished_policies.count(),
        )


class MonitorQuickLink(QuickLinkBase):
    def get_quick_link(self, organization_id):
        organization_monitors = OrganizationMonitor.objects.filter(
            organization_id=organization_id
        )
        total_monitors = organization_monitors.count()
        status_stats = get_monitors_status_stats(organization_monitors)

        return QuickLink(
            id='monitor',
            name='Monitors',
            total=total_monitors,
            data_number=status_stats.get('triggered', 0),
        )


class IntegrationQuickLink(QuickLinkBase):
    def get_quick_link(self, organization_id):
        organization_integrations = ConnectionAccount.objects.filter(
            organization_id=organization_id
        )
        total_integration = organization_integrations.count()

        integrations_with_errors = organization_integrations.filter(status=ERROR)

        return QuickLink(
            id='integration',
            name='Integrations',
            total=total_integration,
            data_number=integrations_with_errors.count(),
        )
