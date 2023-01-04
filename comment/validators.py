from dataclasses import dataclass

from django.core.exceptions import PermissionDenied

from comment.models import Comment


@dataclass
class CommentPermissionValidator:
    app: str
    model: str

    def validate_add(self, user):
        validate(user, self.app, self.model, 'add')

    def validate_change(self, user):
        validate(user, self.app, self.model, 'change')

    def validate_delete(self, user):
        validate(user, self.app, self.model, 'delete')


def validate(user, app, model, operation):
    permission = f'{app}.{operation}_{model}'
    if not user.has_perm(permission):
        raise PermissionDenied


CONTROL = 'control'  # laika-web
POLICY = 'policy'  # laika-web
TASK = 'task'  # laika-web
DRAFT_REPORT = 'draft_report'  # laika-web, audits
EVIDENCE = 'fieldwork_evidence'  # laika-web, audits
REQUIREMENT = 'requirement'  # audits
POPULATION = 'population'  # laika-web, audits

PERMISSIONS = {
    CONTROL: CommentPermissionValidator('control', 'controlcomment'),
    DRAFT_REPORT: CommentPermissionValidator('audit', 'draftreportcomment'),
    TASK: CommentPermissionValidator('program', 'task_comment'),
    EVIDENCE: CommentPermissionValidator('fieldwork', 'evidencecomment'),
    REQUIREMENT: CommentPermissionValidator('fieldwork', 'requirementcomment'),
    POPULATION: CommentPermissionValidator('population', 'populationcomment'),
    POLICY: CommentPermissionValidator('policy', 'policycomment'),
}

DEFAULT_VALIDATOR = CommentPermissionValidator('comment', 'reply')


def permission_validator(comment: Comment) -> CommentPermissionValidator:
    return PERMISSIONS.get(comment_type(comment), DEFAULT_VALIDATOR)


def comment_type(comment: Comment) -> str:
    # TODO: add a migration to add comment type to avoid this lookup
    if comment.control_comments.exists():
        return CONTROL
    elif comment.policy_comments.exists():
        return POLICY
    elif comment.task.exists():
        return TASK
    elif comment.draft_report_comments.exists():
        return DRAFT_REPORT
    elif comment.evidence_comments.exists():
        return EVIDENCE
    elif comment.requirement_comments.exists():
        return REQUIREMENT
    elif comment.population.exists():
        return POPULATION
    else:
        return ''
