from action_item.models import ActionItem
from blueprint.models import ImplementationGuideBlueprint
from control.models import Control, ControlPillar
from evidence.models import Evidence, SystemTagEvidence, Tag
from program.models import Program, SubTask, Task


def create_control(organization, display_id, name, reference_id='XX-01', **kwargs):
    control = Control.objects.create(
        organization=organization,
        display_id=display_id,
        name=name,
        reference_id=reference_id,
        **kwargs
    )
    return control


def get_control(organization, id, **kwargs):
    control = Control.objects.get(id=id, organization=organization, **kwargs)
    return control


def create_control_evidence(control, name, organization, description=''):
    evidence = Evidence.objects.create(
        name=name, description=description, type='FILE', organization=organization
    )
    control.evidence.add(evidence)
    return evidence


def create_control_pillar(name, **kwargs):
    pillar = ControlPillar.objects.create(name=name, **kwargs)
    return pillar


def create_action_item(name, **kwargs):
    return ActionItem.objects.create(name=name, **kwargs)


def create_tag(name, organization):
    tag = Tag.objects.create(name=name, organization=organization)
    return tag


def create_system_tag_evidence(tag, evidence):
    system_tag_evidence = SystemTagEvidence.objects.create(
        tag=tag,
        evidence=evidence,
    )
    return system_tag_evidence


def create_subtask(organization, name=''):
    program = Program.objects.create(
        organization=organization, name='Test program', description=''
    )
    task = Task.objects.create(name=name, description='Test Task', program=program)
    return SubTask.objects.create(
        task=task,
        text='',
        status='completed',
        group='documentation',
        sort_index=1,
        badges='technical',
    )


def create_implementation_guide(**kwargs):
    implementation_guide = ImplementationGuideBlueprint.objects.create(**kwargs)
    return implementation_guide
