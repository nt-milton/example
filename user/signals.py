import logging

from django.db import connection
from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver

from feature.constants import new_training_feature_flag
from monitor.action_item import reconcile_action_items
from user.models import (
    BACKGROUND_CHECK_STATUS_NA,
    DEFAULT_WATCHER_ROLES,
    User,
    WatcherList,
)
from user.utils.compliant import is_user_compliant_completed

logger = logging.getLogger(__name__)


def is_user_promoted(old_instance, new_instance):
    return (
        old_instance.role not in DEFAULT_WATCHER_ROLES
        and new_instance.role in DEFAULT_WATCHER_ROLES
    )


def is_user_demoted(old_instance, new_instance):
    return (
        old_instance.role in DEFAULT_WATCHER_ROLES
        and new_instance.role not in DEFAULT_WATCHER_ROLES
    )


def assign_user_to_watcher_lists_in_organization(user_id, organization_id):
    query = '''
    INSERT INTO user_watcherlist_users
    (watcherlist_id, user_id)
    SELECT wl.id AS watcherlist_id, (%s) AS user_id
    FROM user_watcherlist AS wl
    WHERE wl.organization_id = %s
    ON CONFLICT DO NOTHING;
    '''
    with connection.cursor() as cursor:
        cursor.execute(query, [user_id, str(organization_id).replace('-', '')])


def remove_user_from_watcher_lists_in_organization(user_id):
    query = 'DELETE FROM user_watcherlist_users WHERE user_id = %s;'
    with connection.cursor() as cursor:
        cursor.execute(query, [user_id])


def update_watcher_list(sender, instance: WatcherList, **kwargs):
    reconcile_action_items(instance.organization_monitor)


m2m_changed.connect(update_watcher_list, sender=WatcherList.users.through)


@receiver(pre_save, sender=User, dispatch_uid='assign_to_watcher_list_if_group_matches')
def assign_user_to_watcher_list_if_group_matches(sender, instance, **kwargs):
    old_instance = User.objects.filter(id=instance.id).first()
    if not old_instance:
        return
    if is_user_promoted(old_instance, instance):
        assign_user_to_watcher_lists_in_organization(
            instance.id, instance.organization.id
        )
    if is_user_demoted(old_instance, instance):
        remove_user_from_watcher_lists_in_organization(instance.id)


@receiver(pre_save, sender=User, dispatch_uid='check_compliant_completed')
def check_compliant_completed(sender, instance, **kwargs):
    try:
        old_instance = User.objects.get(id=instance.id)
        training_column_name = 'security_training'
        if old_instance.organization.is_flag_active(new_training_feature_flag):
            training_column_name = 'assigned_trainings_completed'

        if (
            old_instance.background_check_status != instance.background_check_status
            or old_instance.background_check_passed_on
            != instance.background_check_passed_on
            or old_instance.policies_reviewed != instance.policies_reviewed
            or getattr(old_instance, training_column_name)
            != getattr(instance, training_column_name)
        ):
            if instance.background_check_status == BACKGROUND_CHECK_STATUS_NA:
                instance.background_check_passed_on = None
            compliant_completed = is_user_compliant_completed(instance)
            instance.compliant_completed = compliant_completed
    except Exception as error:
        logger.warning(f'Could not update Compliant: {error}')


@receiver(post_save, sender=User, dispatch_uid='assign_new_user_to_watcher_list')
def assign_new_user_to_watcher_list(sender, instance, created, **kwargs):
    if created and instance.role in DEFAULT_WATCHER_ROLES:
        assign_user_to_watcher_lists_in_organization(
            instance.id, instance.organization.id
        )
