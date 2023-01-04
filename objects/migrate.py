import logging
from collections import namedtuple

from django.db import connection

from objects import signals
from objects.models import Attribute, LaikaObjectType

AttributeRename = namedtuple('AttributeRename', ('old', 'new'))
AttributeMerge = namedtuple('AttributeMerge', ('source', 'target'))
logger = logging.getLogger(__name__)


NON_DEFAULT_ATTRIBUTE_FIELDS = ['min_width', 'is_manually_editable']


def migrate_lo(spec, merge=[], new=[], rename=[], delete=[], reorder=False):
    lo_types = LaikaObjectType.objects.filter(
        type_name=spec.type, is_system_type=True
    ).all()
    for lo_type in lo_types:
        merge_attributes(lo_type, merge)
        add_attributes(spec, lo_type, new)
        rename_attributes(lo_type, rename)
        delete_attributes(lo_type, delete)
    if reorder:
        update_attributes_order(spec)
    update_non_default_fields_in_spec_attributes(spec)


def update_non_default_fields_in_spec_attributes(spec):
    for attribute in spec.attributes:
        non_default_attribute_fields = {
            field: attribute[field]
            for field in NON_DEFAULT_ATTRIBUTE_FIELDS
            if field in attribute
        }
        if non_default_attribute_fields:
            Attribute.objects.filter(
                object_type__type_name=spec.type, name=attribute['name']
            ).update(**non_default_attribute_fields)


def add_attributes(spec, lo_type, new_attributes):
    for new_attribute in new_attributes:
        att_specs = [att for att in spec.attributes if att['name'] == new_attribute]
        att_spec = att_specs[0] if att_specs else None
        if att_spec:
            logger.info(f'New attribute for {lo_type} {new_attribute}')
            with connection.cursor() as cursor:
                cursor.execute(_bulk_add(new_attribute), [lo_type.id])
            signals.post_save.disconnect(
                sender=Attribute, dispatch_uid='post_save_attribute'
            )
            Attribute.objects.update_or_create(
                object_type=lo_type, name=new_attribute, defaults=att_spec
            )


def _bulk_add(new_att):
    return f'''
        UPDATE objects_laikaobject
        SET data =  data  || '{{"{new_att}":null}}'::jsonb
        WHERE object_type_id = %s and not data ? '{new_att}';
    '''


def merge_attributes(lo_type, merge_attributes_list):
    for merge in merge_attributes_list:
        logger.info(
            f'Attribute merging for {lo_type} '
            f'{merge.source[0]} and {merge.source[1]} to {merge.target}'
        )
        with connection.cursor() as cursor:
            cursor.execute(
                _bulk_merge(merge.target, merge.source[0], merge.source[1]),
                [lo_type.id],
            )


def _bulk_merge(target_column, source_1, source_2):
    return f'''
        UPDATE objects_laikaobject
        SET data = jsonb_set(
            data,
            '{{"{target_column}"}}',
            to_jsonb(
                cast(coalesce(data->>'{source_1}', '_') as text) || '-' ||
                cast(coalesce(data->>'{source_2}', '_') as text)
            )
        )
        WHERE object_type_id = %s and not data ? 'Key'
    '''


def rename_attributes(lo_type, rename_attributes):
    for rename in rename_attributes:
        logger.info(
            f'Attribute rename for {lo_type} changed from {rename.old} to {rename.new}'
        )
        with connection.cursor() as cursor:
            cursor.execute(_bulk_rename(rename), [lo_type.id])
        Attribute.objects.filter(object_type=lo_type, name=rename.old).update(
            name=rename.new
        )


def _bulk_rename(rename):
    return f'''
        UPDATE objects_laikaobject
        SET data = jsonb_set(data #- '{{{rename.old}}}',
                                        '{{{rename.new}}}',
                                        data#>'{{{rename.old}}}')
        WHERE object_type_id = %s and data ? '{rename.old}';
    '''


def delete_attributes(lo_type, delete_attributes):
    for name in delete_attributes:
        logger.info(f'Deleting Attribute {name} for {lo_type}')
        Attribute.objects.filter(object_type=lo_type, name=name).delete()


def update_attributes_order(spec):
    for attribute in spec.attributes:
        name = attribute['name']
        sort_index = attribute['sort_index']
        logger.info(
            f'Attribute index update for {spec.type}. {name} index set as {sort_index}'
        )
        Attribute.objects.filter(
            object_type__type_name=spec.type, name=attribute['name']
        ).update(sort_index=attribute['sort_index'])
