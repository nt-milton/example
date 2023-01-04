from search.types import CmdKMonitorResultType


def launchpad_mapper(model, organization_id):
    return [
        CmdKMonitorResultType(
            id=organization_monitor.get('id'),
            display_id=organization_monitor.get('monitor__display_id'),
            name=organization_monitor.get('monitor__name'),
            description=organization_monitor.get('monitor__description'),
            url=f"/monitors/{organization_monitor.get('id')}",
        )
        for organization_monitor in model.objects.filter(
            organization_id=organization_id
        ).values('id', 'monitor__display_id', 'monitor__name', 'monitor__description')
    ]
