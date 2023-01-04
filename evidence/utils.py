import evidence.constants as constants
from evidence.models import Evidence, SystemTagEvidence
from laika.cache import cache_func
from program.models import SubTask, SubtaskTag


def delete_evidence_check(organization, evidence, related_models):
    exists_in_relation = False
    for model in related_models:
        exists_in_relation = model.objects.filter(
            evidence__id=evidence.id, evidence__organization=organization
        ).exists()

        if exists_in_relation:
            return

    if not exists_in_relation:
        if Evidence.objects.filter(organization=organization, id=evidence.id).exists():
            Evidence.objects.filter(organization=organization, id=evidence.id).delete()


def get_content_id(e):
    if e.policy and e.type == constants.POLICY:
        return e.policy.id
    return None


def get_file_name_from_path(file_path):
    _, _, _, file_name = file_path.split('/')
    return file_name


# For now I'm putting these functions below
# here because there are some circular
# dependencies between Evidence, Program, Drive not so easy to fix
# but this should go as a model function.


def has_metadata_tag(evidence, tag_value):
    system_tags = SystemTagEvidence.objects.filter(evidence=evidence)
    subtasks = SubTask.objects.filter(id__in=[st.tag.name for st in system_tags])
    has_tags = False
    for st in subtasks.all():
        if st.metadata_tags and tag_value in st.metadata_tags:
            has_tags = True

    return has_tags


@cache_func
def get_evidence_manual_tags(evidence, **kwargs):
    return set(evidence.tags.all())


@cache_func
def tags_associated_to_evidence(evidence, **kwargs):
    related_tags = []
    playbooks = []
    certificates = []
    system_tags = SystemTagEvidence.objects.filter(evidence=evidence)

    subtasks_ids = [st.tag.name for st in system_tags]
    subtask_tags = SubtaskTag.objects.filter(
        subtask__id__in=subtasks_ids, tag__organization=evidence.organization
    )
    tags = []
    for stt in subtask_tags:
        tags.append(stt.tag.name)

    subtasks = SubTask.objects.filter(id__in=subtasks_ids)
    for subtask in subtasks:
        playbooks.append(subtask.playbook_tag)
        certificates.extend(subtask.certificates_tags)
        if subtask.related_subtasks:
            related_tags.extend(subtask.related_subtasks_tags)
            playbooks.extend(subtask.related_subtasks_playbooks)
            certificates.extend(subtask.related_subtasks_certificates)

    return {
        'playbook_tags': set(playbooks),
        'certs_tags': set(certificates),
        'related_tags': set(tags + related_tags),
    }
