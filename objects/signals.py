import logging

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Attribute, LaikaObject

logger = logging.getLogger('objects')


@receiver(post_save, sender=Attribute, dispatch_uid='post_save_attribute')
def sync_laika_objects(sender, instance, created, **kwargs):
    if created:
        logger.info(f'New column for laika object created: {instance}')
        apply_to_laika_objects(instance, add_default_attribute)


def apply_to_laika_objects(attribute, operation, **kwargs):
    laika_objects_to_update = attribute.object_type.elements.all()
    for laika_object in laika_objects_to_update:
        operation(attribute, laika_object, **kwargs)
    LaikaObject.objects.bulk_update(laika_objects_to_update, ['data'], batch_size=1000)


def add_default_attribute(attribute, laika_object):
    laika_object.data[attribute.name] = attribute.metadata.default_value


@receiver(post_delete, sender=Attribute, dispatch_uid='post_delete_attribute')
def remove_deleted_laika_object_attribute(sender, instance, **kwargs):
    apply_to_laika_objects(instance, delete_attribute)


def delete_attribute(attribute, laika_object):
    if attribute.name in laika_object.data:
        del laika_object.data[attribute.name]


@receiver(pre_save, sender=Attribute, dispatch_uid='pre_save_attribute')
def process_laika_object_type_change(sender, instance, **kwargs):
    before = Attribute.objects.filter(pk=instance.id).first()
    if not before:
        return

    if instance.name != before.name:
        logger.info(
            f'Attribute {instance.id} was renamed from {before.name} to {instance.name}'
        )
        apply_to_laika_objects(instance, rename_attribute, before=before)

    elif instance.attribute_type != before.attribute_type:
        logger.info(
            f'Attribute type {instance.id} changed from '
            f'{before.attribute_type} to {instance.attribute_type}'
        )
        # TODO: We need to define all supported types and how they will
        # convert from one type to the other


def rename_attribute(attribute, laika_object, **kwargs):
    before = kwargs.get('before')
    if not before:
        logger.error(
            f'Attribute {attribute.name} on laika object type '
            f'{attribute.object_type.type_name} for organization: '
            f'{attribute.object_type.organization.name} did not have '
            'a previous value'
        )

    value = laika_object.data.get(before.name, attribute.metadata.default_value)
    if before.name in laika_object.data:
        del laika_object.data[before.name]
    laika_object.data[attribute.name] = value
