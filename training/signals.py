import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from laika.cache import cache_func
from training.models import Alumni, Training
from user.models import User
from user.utils.compliant import is_user_compliant_completed

logger = logging.getLogger(__name__)


@cache_func
def get_training_ids_by_role(organization, **kwargs):
    trainings = Training.objects.filter(organization=organization)
    result = {}
    for training in trainings:
        for role in training.roles:
            training_ids = result.get(role, [training.id])
            if training.id not in training_ids:
                training_ids.append(training.id)
            result[role] = training_ids
    return result


def is_security_training_complete(user, training_ids):
    ids = Alumni.objects.filter(training__id__in=training_ids, user=user).values_list(
        'training_id', flat=True
    )
    distinct_ids = set(ids)
    return len(distinct_ids) == len(training_ids)


def update_user_in_memory(user, force_update=False):
    trainings = get_training_ids_by_role(user.organization, force_update=force_update)
    if not trainings.get(user.role):
        return user
    user.security_training = is_security_training_complete(
        user=user, training_ids=trainings[user.role]
    )
    user.compliant_completed = is_user_compliant_completed(user)
    return user


def bulk_save_users(users):
    # It uses bulk since we need to skip the pre_save signal in
    # the user model
    User.objects.bulk_update(users, fields=['compliant_completed', 'security_training'])


@receiver(
    [post_save, post_delete],
    sender=Alumni,
    dispatch_uid='update_user_compliant_completed_post_save',
)
def update_user_fields(sender, instance, **kwargs):
    """
    Updates the user's security training and compliant completed fields
    """
    try:
        user = instance.user
        user = update_user_in_memory(user, force_update=True)
        bulk_save_users([user])
    except Exception as error:
        logger.warning(f'Could not update user fields: {error}')


@receiver(
    [post_save, post_delete],
    sender=Training,
    dispatch_uid='update_user_compliant_post_save_training',
)
def update_user_compliant_fields(sender, instance, **kwargs):
    """
    Updates the user's security training and compliant completed fields
    """
    try:
        users = User.objects.filter(organization=instance.organization)
        force_update = True
        for user in users:
            update_user_in_memory(user, force_update)
            force_update = False
        User.objects.bulk_update(
            users, fields=['compliant_completed', 'security_training']
        )
    except Exception as error:
        logger.warning(f'Could not update user fields: {error}')
