from dashboard.models import DefaultTask
from user.constants import USER_ROLES

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 50

USER_TASKS_BY_ROLE = {
    USER_ROLES['SALESPERSON']: [
        DefaultTask.LIBRARY_TRAINING_VIDEO,
        DefaultTask.DATAROOM_TRAINING_VIDEO,
        DefaultTask.COMPLETE_TRAININGS,
    ],
    USER_ROLES['VIEWER']: [DefaultTask.COMPLETE_TRAININGS],
}

MONITOR_DASHBOARD_TASK_TYPE = 'monitor_task'
