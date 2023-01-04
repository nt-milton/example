from datetime import datetime

from audit.tests.factory import create_audit
from comment.models import Reply
from fieldwork.models import Evidence, EvidenceComment
from program.models import TaskComment


def create_comment(organization, owner, content, task_id, subtask_id):
    return TaskComment.objects.custom_create(
        organization=organization,
        owner=owner,
        content=content,
        task_id=task_id,
        subtask_id=subtask_id,
        tagged_users=[],
    )


def create_reply(owner, comment, content):
    return Reply.objects.create(owner=owner, content=content, parent=comment)


def create_completed_audit(graphql_organization, audit_firm):
    audit = create_audit(
        organization=graphql_organization,
        name='Laika Dev Soc 2 Type 1 Audit 2021',
        audit_firm=audit_firm,
    )
    audit.completed_at = datetime.now()
    audit.save()
    return audit


def create_evidence(
    audit, display_id='2', name='Ev2', instructions='yyyy', status='open', **kwargs
):
    return Evidence.objects.create(
        audit=audit,
        display_id=display_id,
        name=name,
        instructions=instructions,
        status=status,
        **kwargs
    )


def create_evidence_comment(user, evidence, tagged_users=[]):
    return EvidenceComment.objects.custom_create(
        owner=user,
        evidence_id=evidence.id,
        tagged_users=tagged_users,
        content='Commenting',
        is_internal_comment=True,
    )
