from laika.utils.exceptions import ServiceException
from organization.models import Organization
from user.constants import CONCIERGE


def get_organization_by_user_type(user, organization_id) -> Organization:
    user_role = user.role

    if user_role == CONCIERGE:
        organization = Organization.objects.get(id=organization_id)

        if not organization:
            raise ServiceException('Bad Request, some parameters are missing.')
    else:
        organization = user.organization

    return organization
