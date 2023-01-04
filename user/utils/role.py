from user.constants import USER_ROLES


def get_label_role(role_value):
    """
    Returns the label of the role using the value. Otherwise, returns None.
    Ex: the user.role is the value and it's sent as a parameter to get the
    label.
    """
    for key, value in USER_ROLES.items():
        if value == role_value:
            return key.title()

    return None
