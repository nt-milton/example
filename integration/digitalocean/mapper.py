from integration.digitalocean.constants import DIGITALOCEAN, NO
from objects.system_types import Monitor


def map_alert_policy_to_monitor_lo(monitor, connection_name):
    lo_monitor = Monitor()
    description = monitor['description']
    alert_destinations = monitor['alerts']
    slack_destinations = alert_destinations['slack']
    email_destinations = alert_destinations['email']
    lo_monitor.id = monitor['uuid']
    lo_monitor.name = description
    lo_monitor.type = monitor['type']
    lo_monitor.query = f"{description} {monitor['compare']} {monitor['value']}"
    lo_monitor.tags = monitor['tags']
    lo_monitor.message = description
    lo_monitor.overall_state = monitor['enabled']
    lo_monitor.created_at = NO
    lo_monitor.created_by_name = NO
    lo_monitor.created_by_email = NO
    lo_monitor.notification_type = (
        email_destinations if email_destinations else slack_destinations
    )
    lo_monitor.destination = (
        slack_destinations if slack_destinations else email_destinations
    )
    lo_monitor.source_system = DIGITALOCEAN
    lo_monitor.connection_name = connection_name
    return lo_monitor.data()
