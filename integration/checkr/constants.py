from user.models import (
    BACKGROUND_CHECK_STATUS_CANCELLED,
    BACKGROUND_CHECK_STATUS_EXPIRED,
    BACKGROUND_CHECK_STATUS_FLAGGED,
    BACKGROUND_CHECK_STATUS_PASSED,
    BACKGROUND_CHECK_STATUS_PENDING,
    BACKGROUND_CHECK_STATUS_SUSPENDED,
)

CHECKR_ENDPOINTS = {
    'account_details': {'url': 'account', 'method': 'get_account_details'},
    'create_candidates': {
        'url': 'candidates',
        'method': 'create_candidate_and_send_invitation',
    },
    'list_nodes': {'url': 'nodes', 'method': 'get_nodes'},
    'list_packages': {'url': 'packages', 'method': 'get_packages'},
}

REPORT_TYPE = 'report'
INVITATION_TYPE = 'invitation'
CANDIDATE_CREATED_TYPE = 'candidate.created'
CANDIDATE_UPDATED_TYPE = 'candidate.updated'

INVITATION_CREATED_TYPE = 'invitation.created'
INVITATION_COMPLETED_TYPE = 'invitation.completed'
INVITATION_DELETED_TYPE = 'invitation.deleted'
INVITATION_EXPIRED_TYPE = 'invitation.expired'

REPORT_UPDATED_TYPE = 'report.updated'
REPORT_CREATED_TYPE = 'report.created'
REPORT_COMPLETED_TYPE = 'report.completed'
REPORT_SUSPENDED_TYPE = 'report.suspended'
REPORT_ENGAGED_TYPE = 'report.engaged'
REPORT_RESUMED_TYPE = 'report.resumed'
REPORT_DISPUTED_TYPE = 'report.disputed'
REPORT_CANCELED_TYPE = 'report.canceled'
REPORT_POST_ADVERSE_TYPE = 'report.post_adverse_action'
REPORT_PRE_ADVERSE_TYPE = 'report.pre_adverse_action'

ACCOUNT_CREDENTIALED_TYPE = 'account.credentialed'
TOKEN_DEAUTHORIZED = 'token.deauthorized'

PENDING_CHECKR_STATUS = 'pending'
CANCELED_CHECKR_STATUS = 'canceled'
COMPLETE_CHECKR_STATUS = 'complete'
CLEAR_CHECKR_STATUS = 'clear'
CONSIDER_CHECKR_STATUS = 'consider'
COMPLETED_CHECKR_INVITATION_STATUS = 'completed'
EXPIRED_CHECKR_STATUS = 'expired'
DELETED_CHECKR_STATUS = 'deleted'
RESUMED_CHECKR_STATUS = 'resumed'
DISPUTED_CHECKR_STATUS = 'disputed'
SUSPENDED_CHECKR_STATUS = 'suspended'

PENDING_STATUS = 'Pending'
SUSPENDED_STATUS = 'Suspended'
CLEAR_STATUS = 'Clear'
PASSED_STATUS = 'Passed'
CANCELED_STATUS = 'Canceled'
INVITATION_SENT_STATUS = 'Invitation Sent'
INVITATION_CANCELED_STATUS = 'Invitation Canceled'
INVITATION_EXPIRED_STATUS = 'Invitation Expired'
NOT_ELIGIBLE_STATUS = 'Not Eligible'
NEEDS_REVIEW_STATUS = 'Needs Review'
HIERARCHY_ERROR_MSG = 'Sorry, your account is not enabled for segmentation'
HIERARCHY_ERROR_CODE = 403

CHECKR_STATUS_MAP = {
    INVITATION_CREATED_TYPE: {
        PENDING_CHECKR_STATUS: {
            "lo_status": INVITATION_SENT_STATUS,
            "people_status": BACKGROUND_CHECK_STATUS_PENDING,
        }
    },
    INVITATION_COMPLETED_TYPE: {
        COMPLETED_CHECKR_INVITATION_STATUS: {
            "lo_status": PENDING_STATUS,
            "people_status": BACKGROUND_CHECK_STATUS_PENDING,
        }
    },
    INVITATION_EXPIRED_TYPE: {
        INVITATION_EXPIRED_STATUS: {
            "lo_status": INVITATION_CANCELED_STATUS,
            "people_status": BACKGROUND_CHECK_STATUS_EXPIRED,
        }
    },
    INVITATION_DELETED_TYPE: {
        DELETED_CHECKR_STATUS: {
            "lo_status": INVITATION_EXPIRED_STATUS,
            "people_status": BACKGROUND_CHECK_STATUS_FLAGGED,
        }
    },
    REPORT_CREATED_TYPE: {
        PENDING_CHECKR_STATUS: {
            "lo_status": PENDING_STATUS,
            "people_status": BACKGROUND_CHECK_STATUS_PENDING,
        }
    },
    REPORT_COMPLETED_TYPE: {
        COMPLETE_CHECKR_STATUS: {
            "complete": {
                "lo_status": CLEAR_STATUS,
                "people_status": BACKGROUND_CHECK_STATUS_PASSED,
            },
            "clear": {
                "lo_status": CLEAR_STATUS,
                "people_status": BACKGROUND_CHECK_STATUS_PASSED,
            },
            "consider": {
                "lo_status": NEEDS_REVIEW_STATUS,
                "people_status": BACKGROUND_CHECK_STATUS_PENDING,
            },
            "canceled": {
                "lo_status": CANCELED_STATUS,
                "people_status": BACKGROUND_CHECK_STATUS_CANCELLED,
            },
        },
        CLEAR_CHECKR_STATUS: {
            "clear": {
                "lo_status": PASSED_STATUS,
                "people_status": BACKGROUND_CHECK_STATUS_PASSED,
            }
        },
        CONSIDER_CHECKR_STATUS: {
            "consider": {
                "lo_status": NEEDS_REVIEW_STATUS,
                "people_status": BACKGROUND_CHECK_STATUS_PENDING,
            }
        },
    },
    REPORT_PRE_ADVERSE_TYPE: {
        COMPLETE_CHECKR_STATUS: {
            "lo_status": PENDING_STATUS,
            "people_status": BACKGROUND_CHECK_STATUS_PENDING,
        }
    },
    REPORT_POST_ADVERSE_TYPE: {
        COMPLETE_CHECKR_STATUS: {
            "lo_status": NOT_ELIGIBLE_STATUS,
            "people_status": BACKGROUND_CHECK_STATUS_FLAGGED,
        }
    },
    REPORT_ENGAGED_TYPE: {
        COMPLETE_CHECKR_STATUS: {
            "lo_status": PENDING_STATUS,
            "people_status": BACKGROUND_CHECK_STATUS_FLAGGED,
        }
    },
    REPORT_SUSPENDED_TYPE: {
        SUSPENDED_CHECKR_STATUS: {
            "lo_status": SUSPENDED_STATUS,
            "people_status": BACKGROUND_CHECK_STATUS_SUSPENDED,
        }
    },
    REPORT_RESUMED_TYPE: {
        RESUMED_CHECKR_STATUS: {
            "lo_status": PENDING_STATUS,
            "people_status": BACKGROUND_CHECK_STATUS_PENDING,
        }
    },
    REPORT_DISPUTED_TYPE: {
        "disputed": {
            "lo_status": PENDING_STATUS,
            "people_status": BACKGROUND_CHECK_STATUS_PENDING,
        }
    },
    REPORT_CANCELED_TYPE: {
        CANCELED_CHECKR_STATUS: {
            "lo_status": CANCELED_STATUS,
            "people_status": BACKGROUND_CHECK_STATUS_CANCELLED,
        }
    },
    REPORT_UPDATED_TYPE: {
        PENDING_CHECKR_STATUS: {
            "lo_status": PENDING_STATUS,
            "people_status": BACKGROUND_CHECK_STATUS_PENDING,
        },
        CLEAR_CHECKR_STATUS: {
            "lo_status": PENDING_STATUS,
            "people_status": BACKGROUND_CHECK_STATUS_PENDING,
        },
    },
}
