from search.types import CmdKUserResultType


def launchpad_mapper(model, organization_id):
    return [
        CmdKUserResultType(
            id=user.get("id"),
            username=user.get("username"),
            name=f"{user.get('first_name')} {user.get('last_name')}",
            email=user.get('email'),
            url=f"/people?userId={user.get('username')}",
        )
        for user in model.objects.filter(
            organization_id=organization_id, username__isnull=False
        )
        .exclude(username__exact='')
        .values('id', 'username', 'first_name', 'last_name', 'email')
    ]
