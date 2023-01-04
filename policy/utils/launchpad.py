from search.types import CmdKPolicyResultType


def launchpad_mapper(model, organization_id):
    return [
        CmdKPolicyResultType(
            id=policy.get('id'),
            display_id=f"P-{policy.get('display_id')}",
            description=policy.get('description'),
            name=policy.get('name'),
            url=f"/policies/{policy.get('id')}",
            text=policy.get('policy_text'),
        )
        for policy in model.objects.filter(organization_id=organization_id).values(
            'id', 'display_id', 'description', 'name', 'policy_text'
        )
    ]
