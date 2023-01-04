from user.constants import USER_ROLES


def is_same_user(logged_user, user):
    if user:
        return logged_user.email == user.email


mapper = {
    'user': {
        'user.change_user': 'canUpdate',
        'user.delete_user': 'canRemove',
        'user.add_user': 'canInvite',
        'user.view_user': 'canRead',
    },
    'organization': {
        'organization.change_organization': 'canUpdate',
        'organization.view_organization': 'canRead',
    },
    'policy': {
        'policy.unpublish_policy': 'canUnpublish',
        'policy.add_policy': 'canCreate',
        'policy.publish_policy': 'canPublish',
        'policy.delete_policy': 'canDelete',
        'policy.view_policy': 'canRead',
        'policy.batch_delete_policy': 'canBatchDelete',
        'policy.change_policy': 'canUpdate',
    },
    'control': {
        'control.batch_delete_control': 'canBatchDelete',
        'control.add_control': 'canCreate',
        'control.view_control': 'canRead',
        'control.delete_control': 'canDelete',
        'control.associate_user': 'canAssociate',
        'control.change_control': 'canUpdate',
        'control.change_control_status': 'canChangeStatus',
    },
}


def valid_control_permission(logged_user, permission, users):
    is_OOA = any(is_same_user(logged_user, u) for u in users)

    is_valid_user = logged_user.role != USER_ROLES.get('CONTRIBUTOR') or is_OOA
    return permission and (permission != 'canDelete' or is_valid_user)


def map_permissions(logged_user, entity_name, users=[None]):
    user_permissions = []

    entity_permissions = [
        p for p in logged_user.get_all_permissions() if f'{entity_name}.' in p
    ]
    entity_mapper = mapper.get(entity_name)
    for p in entity_permissions:
        permission = entity_mapper.get(p)

        if entity_name != 'control':
            if permission and (
                permission != 'canRemove'
                or (len(users) and not is_same_user(logged_user, users[0]))
            ):
                user_permissions.append(permission)
        elif valid_control_permission(logged_user, permission, users):
            user_permissions.append(permission)

    if logged_user.organization:
        user_permissions.append(f'tier_{logged_user.organization.tier.lower()}')
    return user_permissions
