from comment.models import Comment
from fieldwork.models import EvidenceComment


def create_evidence_comment_with_pool(owner, content, evidence, pool):
    comment = Comment.objects.create(owner=owner, content=content)

    EvidenceComment.objects.create(evidence=evidence, comment=comment, pool=pool)
    return comment
