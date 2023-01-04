from feature.constants import new_training_feature_flag
from user.models import BACKGROUND_CHECK_STATUS_NA, BACKGROUND_CHECK_STATUS_PASSED, User


def is_user_compliant_completed(user: User) -> bool:
    # If the passed user is compliant completed return true otherwise false
    # Validation of: Policies Reviewed, Security Training
    # and Background Status equals to passed or na

    training_column_name = 'security_training'
    if user.organization.is_flag_active(new_training_feature_flag):
        training_column_name = 'assigned_trainings_completed'

    return (
        user.policies_reviewed
        and getattr(user, training_column_name)
        and (
            user.background_check_status == BACKGROUND_CHECK_STATUS_NA
            or (
                user.background_check_status == BACKGROUND_CHECK_STATUS_PASSED
                and user.background_check_passed_on is not None
            )
        )
    )
