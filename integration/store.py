import logging
import timeit
from collections import namedtuple
from typing import Callable, Dict, Generator, List, Union

from integration.integration_utils.raw_objects_utils import replace_unsupported_unicode
from integration.log_utils import connection_context, time_metric
from integration.models import ConnectionAccount
from integration.test_mode import is_connection_on_test_mode
from objects.models import LaikaObject, LaikaObjectType
from objects.system_types import EVENT, ObjectTypeSpec, resolve_laika_object_type

Mapper = namedtuple('Mapper', ('map_function', 'laika_object_spec', 'keys'))

logger = logging.getLogger(__name__)


def _build_criteria(keys, data):
    return {f'data__{key}': data[key] for key in keys}


def _map_raw_objects(alias, map_function):
    def create_object(raw):
        try:
            return map_function(raw, alias)
        except Exception as err:
            logger.warning(f'raw data with issues: {raw}')
            raise ValueError(f'Mapping error raw: {raw}') from err

    return create_object


def _get_mapped_data(
    mapper: Mapper, raw: Dict, connection_account: ConnectionAccount
) -> Union[Dict, None]:
    try:
        return mapper.map_function(raw, connection_account.alias)
    except Exception as err:
        logger.warning(
            f'Connection account {connection_account.id} - '
            f'Mapping error raw: {raw}, error: {err}'
        )
        logger.warning(f'raw data with issues: {raw}')
        raise ValueError(f'Mapping error raw: {raw}') from err


def _get_object_search_criteria(
    mapper: Mapper, laika_object_type: LaikaObjectType, data: Dict
) -> Dict:
    return {**_build_criteria(mapper.keys, data), 'object_type': laika_object_type}


def clean_up_by_criteria(connection_account, spec: ObjectTypeSpec, lookup_query: dict):
    with time_metric('cleanup_objects'):
        keys = get_keep_ids_based_on_lookup_filter(
            connection_account,
            spec,
            lookup_query,
        )
        laika_object_type = resolve_laika_object_type(
            connection_account.organization, spec
        )
        connection_account.clean_up_laika_objects(
            keep_ids=keys,
            laika_object_type=laika_object_type,
            soft_delete=True,
        )


def build_search(
    connection_account: ConnectionAccount,
    mapper: Mapper,
    laika_object_type: LaikaObjectType,
) -> tuple[Callable, Callable]:
    def search(data: dict):
        results = list(
            LaikaObject.objects.filter(
                **_get_object_search_criteria(mapper, laika_object_type, data)
            )[:1]
        )
        return results[0] if results else None

    def empty_update(lo: LaikaObject):
        return None

    if not is_optimized_search(connection_account, laika_object_type):
        return search, empty_update
    data_id_to_lo_id = _event_ids_to_lo(connection_account.id, laika_object_type.id)

    def search_v2(data: dict):
        if data['Id'] not in data_id_to_lo_id:
            return None
        return LaikaObject.objects.get(id=data_id_to_lo_id[data['Id']])

    def update_search(lo: LaikaObject):
        data_id_to_lo_id[lo.data['Id']] = lo.id

    return search_v2, update_search


def update_laika_objects(
    connection_account: ConnectionAccount,
    mapper: Mapper,
    raw_objects: Union[Generator, List],
    cleanup_objects: bool = True,
    escape_characters: bool = False,
) -> List:
    keys: List = []
    if is_connection_on_test_mode(connection_account.id):
        logger.info('Not running update_laika_objects due in testing mode')
        return keys
    start_time = timeit.default_timer()
    laika_object_type: LaikaObjectType = resolve_laika_object_type(
        organization=connection_account.organization, spec=mapper.laika_object_spec
    )
    search, update_search = build_search(connection_account, mapper, laika_object_type)
    for raw in raw_objects:
        with time_metric('map_objects'):
            if escape_characters:
                raw = replace_unsupported_unicode(raw=raw)
            data = _get_mapped_data(
                mapper=mapper, raw=raw, connection_account=connection_account
            )
            if not data:
                continue
        with time_metric('store_objects'):
            with time_metric('search_objects'):
                lo = search(data)
            if lo:
                lo.data = data
                lo.connection_account = connection_account
                lo.deleted_at = None
                lo.save()
            else:
                lo = LaikaObject.objects.create(
                    connection_account=connection_account,
                    object_type=laika_object_type,
                    data=data,
                    deleted_at=None,
                )
                update_search(lo)

            keys.append(lo.id)

    with time_metric('cleanup_objects'):
        if cleanup_objects:
            connection_account.clean_up_laika_objects(
                keep_ids=keys,
                laika_object_type=laika_object_type,
                soft_delete=True,
            )
    map_and_update_operation_time = timeit.default_timer() - start_time
    logger.info(
        f'Connection account {connection_account.id} - Mapping and '
        f'creating/updating laika objects on #{len(keys)} objects '
        f'on LO type {mapper.laika_object_spec.display_name} '
        f'operation took {map_and_update_operation_time} seconds'
    )
    return keys


def get_keep_ids_based_on_lookup_filter(
    connection_account: ConnectionAccount,
    laika_object_spec: ObjectTypeSpec,
    lookup_query: Dict,
):
    execution_time = timeit.default_timer()
    laika_object_type = resolve_laika_object_type(
        connection_account.organization, laika_object_spec
    )
    keep_objects_ids = LaikaObject.objects.filter(
        connection_account=connection_account,
        object_type=laika_object_type,
        deleted_at=None,
        **lookup_query,
    ).values_list('id', flat=True)

    logger.info(
        f'Connection account {connection_account.id} - Function that get the keep IDs '
        f'operation took { timeit.default_timer() - execution_time} seconds.'
    )
    return keep_objects_ids


def is_optimized_search(
    connection_account: ConnectionAccount, laika_object_type: LaikaObjectType
) -> bool:
    search_type = connection_account.integration.metadata.get('search', 'v2')
    return search_type == 'v2' and laika_object_type.type_name == EVENT.type


def _event_ids_to_lo(connection_account_id: int, type_id: int) -> dict[str, int]:
    context = connection_context.get()
    if context and context.object_cache:
        return context.object_cache
    with time_metric('search_objects'):
        start_time = timeit.default_timer()
        data_id_to_lo_id = dict(
            LaikaObject.objects.filter(object_type_id=type_id).values_list(
                'data__Id', 'id'
            )
        )
        operation_time = timeit.default_timer() - start_time
        logger.info(
            f'Connection account {connection_account_id} - Loading data ids '
            f'operation took {operation_time} seconds'
        )
        if context:
            context.object_cache = data_id_to_lo_id
        return data_id_to_lo_id
