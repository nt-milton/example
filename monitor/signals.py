from django.db.models import Q
from django.db.models.functions import Lower
from django.db.models.signals import post_save
from django.dispatch import receiver

from control.models import Control
from monitor.action_item import reconcile_action_items
from monitor.models import MonitorSubscriptionEventType
from organization.models import Organization
from tag.models import Tag
from user.models import DEFAULT_WATCHER_ROLES, User, WatcherList

from .models import Monitor, OrganizationMonitor


@receiver(post_save, sender=OrganizationMonitor)
def update_org_monitor(sender, instance: OrganizationMonitor, created: bool, **kwargs):
    if created:
        if instance.monitor.tag_references:
            set_monitor_tags(instance)
        set_monitor_controls(instance)
    if instance.watcher_list is None:
        set_monitor_watcher_list(instance)


@receiver(post_save, sender=Monitor)
def update_org_controls(sender, instance: Monitor, **kwargs):
    for org_monitor in instance.organization_monitors.all():
        if not instance.control_references and not instance.control_reference_ids:
            org_monitor.controls.clear()
        else:
            set_monitor_controls(org_monitor)

        if not instance.tag_references:
            org_monitor.tags.clear()
        else:
            set_monitor_tags(org_monitor)
        reconcile_action_items(org_monitor)


def create_q_object(references: list, field_name: str):
    value_in = Q()
    for n in references:
        value_in = value_in | Q(**{field_name: n})
    return value_in


def set_monitor_controls(organization_monitor: OrganizationMonitor):
    monitor = organization_monitor.monitor
    if not monitor.control_references and not monitor.control_reference_ids:
        return None
    ids = (
        monitor.control_reference_ids.splitlines()
        if monitor.control_reference_ids
        else ''
    )
    names = (
        monitor.control_references.splitlines() if monitor.control_references else ''
    )
    q_name = create_q_object(names, 'name__iexact')
    q_reference_id = create_q_object(ids, 'reference_id__iexact')
    controls = Control.objects.filter(
        organization=organization_monitor.organization
    ).filter(q_name | q_reference_id)
    organization_monitor.controls.set(controls)


def set_monitor_tags(organization_monitor: OrganizationMonitor):
    tag_names = organization_monitor.monitor.tag_references.splitlines()
    tags = Tag.objects.annotate(name_lower=Lower('name')).filter(
        organization=organization_monitor.organization,
        name_lower__in=[name.lower() for name in tag_names],
    )
    existing_tags = {tag.name.lower() for tag in tags}
    new_tags = create_missing_tags(tag_names, existing_tags, organization_monitor)
    organization_monitor.tags.set(list(tags) + new_tags)


SUBSCRIBED = MonitorSubscriptionEventType.SUBSCRIBED
UNSUBSCRIBED = MonitorSubscriptionEventType.UNSUBSCRIBED


def get_monitor_default_group(organization: Organization):
    users = User.objects.filter(organization=organization)
    default_users = set(users.filter(role__in=DEFAULT_WATCHER_ROLES))
    subscribed_users = set(
        users.filter(monitor_subscription_event__event_type=SUBSCRIBED)
    )
    unsubscribed_users = set(
        users.filter(monitor_subscription_event__event_type=UNSUBSCRIBED)
    )
    return (default_users | subscribed_users) - unsubscribed_users


def set_monitor_watcher_list(organization_monitor: OrganizationMonitor):
    organization = organization_monitor.organization
    default_group = get_monitor_default_group(organization)
    organization_monitor.watcher_list = WatcherList.objects.create(
        organization=organization,
        name=organization_monitor.monitor.name,
    )
    organization_monitor.save()
    organization_monitor.watcher_list.users.set(default_group)


def create_missing_tags(
    tag_names: list, existing_tags: set, organization_monitor: OrganizationMonitor
) -> list:
    missing_tags = list({tag for tag in tag_names if tag.lower() not in existing_tags})
    organization = organization_monitor.organization
    return [
        Tag.objects.create(name=name, organization=organization)
        for name in missing_tags
    ]
