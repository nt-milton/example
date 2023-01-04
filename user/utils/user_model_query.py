from user.models import User


def find_user_by_id_type(id, info):
    """
    Returns an user using id or the username. If the id is digit it uses
    the id property. Otherwise, it uses username property.
    """

    filters = {'organization_id': info.context.user.organization_id}
    user_key = 'username'
    if id.isdigit():
        user_key = 'id'
    filters.update({user_key: id})

    return User.objects.get(**filters)
