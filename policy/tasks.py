from laika.celery import app as celery_app
from laika.utils.ai.embeddings import generate_policy_embedding
from policy.models import Policy


@celery_app.task(name='Create Policy Embeddings')
def generate_policy_embeddings_task(policy_id: str):
    policy = Policy.objects.get(id=policy_id)
    generate_policy_embedding(policy)
