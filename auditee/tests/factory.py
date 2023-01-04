from alert.constants import ALERT_TYPES
from alert.models import Alert
from comment.models import Comment, CommentAlert
from population.models import PopulationComment
from user.models import User


def create_evidence_mention_alert(
    audit_user: User, comment: Comment, graphql_user: User
):
    alert = Alert.objects.create(
        sender=audit_user, receiver=graphql_user, type=ALERT_TYPES['EVIDENCE_MENTION']
    )
    CommentAlert.objects.create(alert=alert, comment=comment)


def create_population_comments_for_pools(population, comment, pools):
    for pool in pools:
        PopulationComment.objects.create(
            population=population, comment=comment, pool=pool
        )
