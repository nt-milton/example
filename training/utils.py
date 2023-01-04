from django.db.models import Q

from training.models import Alumni, Training


def has_trainings_assigned_completed(user, exclude_id=None):
    """
    Checks if the user has completed all the trainings assigned.
    The exclude_id is useful for the pre_save signal in Alumni model.
    It excludes the id that is being updating.
    """

    if user is None:
        return False
    training_ids = (
        Training.objects.filter(organization_id=user.organization_id)
        .filter(Q(roles__contains=user.role))
        .values_list('id', flat=True)
    )

    if exclude_id:
        training_ids.exclude(id=exclude_id)
    user_training_ids = list(training_ids)

    return Alumni.objects.filter(
        training__id__in=user_training_ids, user_id=user.id
    ).values_list('id', flat=True).count() == len(training_ids)
