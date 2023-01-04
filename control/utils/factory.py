from access_review.mutations import RECURRENT_ACTION_ITEM
from access_review.utils import get_access_review_tray_keys
from action_item.utils import get_recurrent_last_action_item
from feature.constants import background_check_feature_flag
from objects.utils import get_bgc_tray_keys

BGC_ACTION_ITEM_CODE = "PS-S-023"


def create_tray_keys_by_reference_id(reference_id, organization):
    if is_ac_action_item(reference_id, organization):
        return get_access_review_tray_keys(organization)

    if reference_id == BGC_ACTION_ITEM_CODE and organization.is_flag_active(
        background_check_feature_flag
    ):
        return get_bgc_tray_keys()

    return None, None, None


def is_ac_action_item(reference_id, organization):
    ac_action_item = get_recurrent_last_action_item(
        RECURRENT_ACTION_ITEM, organization.id
    )
    return (
        ac_action_item
        and ac_action_item.metadata
        and reference_id == ac_action_item.metadata.get('referenceId')
    )
