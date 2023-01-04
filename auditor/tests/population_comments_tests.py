import pytest

from auditor.tests.queries import GET_AUDITOR_POPULATION_COMMENTS
from fieldwork.types import PopulationCommentPoolsEnum
from population.models import PopulationComment

COMMENT_CONTENT = 'My comment'


@pytest.mark.functional(permissions=['comment.view_comment'])
def test_get_auditor_population_comments(
    graphql_audit_client, laika_admin_user, audit_population
):
    PopulationComment.objects.custom_create(
        owner=laika_admin_user,
        population_id=audit_population.id,
        tagged_users=[],
        content=COMMENT_CONTENT,
        pool=PopulationCommentPoolsEnum.All.value,
    )
    response = graphql_audit_client.execute(
        GET_AUDITOR_POPULATION_COMMENTS,
        variables={
            'auditId': audit_population.audit.id,
            'populationId': audit_population.id,
            'pool': PopulationCommentPoolsEnum.All.name,
        },
    )
    assert len(response['data']['auditorPopulationComments']) == 1
