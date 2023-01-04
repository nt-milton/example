import logging

from django.db import connection

from objects.models import LaikaObjectType
from objects.system_types import BACKGROUND_CHECK, USER

logger = logging.getLogger(__name__)


def get_users_relation_with_lo(organization_id):
    with connection.cursor() as cursor:
        cursor.execute(build_user_relation_with_lo(organization_id))
        return cursor.fetchall()


def build_user_relation_with_lo(organization_id):
    return f'''
        SELECT
        u.id, u.email, lo.data->>'Id' as user_lo_id,
        lo.object_type_id as lo_type_id
        FROM user_user AS u
        RIGHT JOIN objects_laikaobject AS lo
            ON (
                cast (
                    lo.data->'Link to People Table'->>'email' as VARCHAR
                ) = u.email and
                lo.object_type_id = (
                    SELECT
                    id
                    FROM objects_laikaobjecttype
                    WHERE type_name = '{BACKGROUND_CHECK.type}'
                    AND organization_id = '{organization_id}'
                )
        )
        where u.organization_id = '{organization_id}'
        union all
        SELECT
        u.id, u.email, lo.data->>'Id' as user_lo_id,
        lo.object_type_id as lo_type_id
        FROM user_user AS u
        RIGHT JOIN objects_laikaobject AS lo
            ON (
                unaccent(TRIM(lo.data->>'Email')) = u.email and
                lo.object_type_id = (
                    SELECT
                    id
                    FROM objects_laikaobjecttype
                    WHERE type_name = '{USER.type}'
                    AND organization_id = '{organization_id}'
                )
        )
        where u.organization_id = '{organization_id}'
    '''


def get_user_lo_associations(organization_id):
    """
    Build a dictionary in order to group the lo types linked with the user.

    Return the dictionary.
    Ex:
    {
        276: {'background_check': [1], 'user': [2]},
        122: {'user': [2]}
    }
    """
    results = get_users_relation_with_lo(organization_id)
    object_types = LaikaObjectType.objects.filter(
        organization_id=organization_id
    ).values_list('id', 'type_name')
    object_types_obj = {key: value for key, value in object_types}

    users_with_lo = {}

    for row in results:
        lo_by_user = users_with_lo.setdefault(row[0], {})
        lo_type = lo_by_user.setdefault(object_types_obj.get(row[3], -1), [])
        lo_type.append(row[2])

    return users_with_lo
