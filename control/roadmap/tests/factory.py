from control.models import ControlGroup, RoadMap


def create_roadmap(organization, **kwargs):
    roadmap = RoadMap.objects.create(organization=organization, **kwargs)
    return roadmap


def create_control_group(roadmap, sort_order=0, **kwargs):
    control_group = ControlGroup.objects.create(
        roadmap=roadmap, sort_order=sort_order, **kwargs
    )
    return control_group


def get_control_group(id, roadmap, **kwargs):
    control_group = ControlGroup.objects.get(id=id, roadmap=roadmap, **kwargs)
    return control_group
