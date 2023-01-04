from search.types import CmdKEvidenceRequestResultType


def launchpad_mapper(model, organization_id):
    return [
        CmdKEvidenceRequestResultType(
            id=f"{er.get('audit_id')}-{er.get('id')}",
            display_id=er.get("display_id"),
            name=er.get('name'),
            description=er.get('audit__name'),
            url=f"/audits/{er.get('audit_id')}/evidence-detail/{er.get('id')}",
        )
        for er in model.objects.filter(
            audit__organization_id=organization_id,
            is_deleted=False,
            status__in=['open', 'submitted'],
        ).values('id', 'display_id', 'audit_id', 'name', 'audit__name')
    ]
