from unittest.mock import patch

import pytest

from concierge.tests import CREATE_CONCIERGE_REQUEST, GET_CONCIERGE_LIST


@pytest.mark.skipif(
    True,
    reason='''Concierge needs to have its own graphql_client
            as in audits and not use the one from LW because the
            authentication will fail''',
)
@pytest.mark.functional(permissions=['user.view_concierge'])
def test_resolve_concierge_list(graphql_client):
    response = graphql_client.execute(GET_CONCIERGE_LIST)
    assert response['data']['conciergeList'] == 'Concierge List'


@pytest.mark.skipif(
    True,
    reason='''Concierge needs to have its own graphql_client
            as in audits and not use the one from LW because the
            authentication will fail''',
)
@pytest.mark.functional(permissions=['user.view_concierge'])
def test_export_ddp(jwt_http_client):
    response = jwt_http_client.get('/concierge/123/ddp/export?playbooks=1234')
    assert response.status_code == 200


@pytest.mark.functional()
@patch('concierge.schema.slack.post_message')
def test_create_concierge_request(post_message_mock, graphql_client):
    execute = graphql_client.execute(
        CREATE_CONCIERGE_REQUEST,
        variables={
            'input': dict(
                requestType='Help with a Diligence Questionnaire',
                description='Request help test',
            )
        },
    )

    post_message_mock.assert_called_once()

    response = execute['data']['createConciergeRequest']
    assert response['conciergeRequest']['id'] == '1'
    assert response['conciergeRequest']['description'] == 'Request help test'
