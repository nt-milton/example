from search.types import CmdKControlResultType


def launchpad_mapper(model, organization_id):
    return [
        CmdKControlResultType(
            id=control.get("id"),
            reference_id=control.get("reference_id"),
            description=control.get("description"),
            name=control.get('name'),
            url=f"/controls/{control.get('id')}",
        )
        for control in model.objects.filter(organization_id=organization_id).values(
            'id', 'name', 'description', 'reference_id'
        )
    ]
