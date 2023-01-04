from user.constants import USER_ROLES

LIBRARY_TRAINING_VIDEO = 'library_training_video'
DATAROOM_TRAINING_VIDEO = 'dataroom_training_video'
COMPLETE_TRAININGS = 'complete_trainings'

TYPE_QUICK_START = 'quick_start'
TYPE_CONTROL = 'control'
TYPE_POLICY = 'policy'
TYPE_ACCESS_REVIEW = 'access_review'

USER_DEFAULT_TASK = {
    LIBRARY_TRAINING_VIDEO: {
        'description': 'Watch the Library Training Video',
        'type': TYPE_QUICK_START,
        'subtype': 'video',
        'task_metadata': {
            "title": "Library Training Video",
            "url": "https://www.youtube.com/embed/uLy5nWL02uc",
        },
    },
    DATAROOM_TRAINING_VIDEO: {
        'description': 'Watch the Dataroom Training Video',
        'type': TYPE_QUICK_START,
        'subtype': 'video',
        'task_metadata': {
            "title": "Dataroom Training Video",
            "url": "https://www.youtube.com/embed/8XoE_2nbNXI",
        },
    },
    COMPLETE_TRAININGS: {
        'description': 'Complete Trainings',
        'type': TYPE_QUICK_START,
        'subtype': 'training',
        'task_metadata': {},
    },
}

USER_TASKS_BY_ROLE = {
    USER_ROLES['SALESPERSON']: [
        LIBRARY_TRAINING_VIDEO,
        DATAROOM_TRAINING_VIDEO,
        COMPLETE_TRAININGS,
    ],
    USER_ROLES['VIEWER']: [COMPLETE_TRAININGS],
}


ACTION_ITEM_COMPLETED_EVENT = 'ActionItemCompleted'
ACTION_ITEM_EDAS_HEALTH_CHECK = 'ActionItemEdasHealthCheck'
