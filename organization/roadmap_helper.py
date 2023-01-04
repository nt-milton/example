from django.db.models import QuerySet

from control.constants import STATUS
from control.models import Control, ControlGroup


def get_roadmap_groups_total_controls(roadmap_groups: QuerySet[ControlGroup]) -> int:
    return sum(group.controls.count() for group in roadmap_groups)


def get_roadmap_groups_implemented_controls(
    roadmap_groups: QuerySet[ControlGroup],
) -> int:
    implemented_controls = 0
    for group in roadmap_groups:
        implemented_controls += sum(
            control.status.upper() == STATUS['IMPLEMENTED']
            for control in group.controls.all()
        )

    return implemented_controls


def get_roadmap_backlog_total_controls(controls: QuerySet[Control]) -> int:
    return controls.count()


def get_roadmap_backlog_implemented_controls(controls: QuerySet[Control]) -> int:
    return sum(control.status.upper() == STATUS['IMPLEMENTED'] for control in controls)
