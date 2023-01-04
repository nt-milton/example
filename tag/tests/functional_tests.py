import json

import pytest

from tag.models import Tag
from tag.tests.mutations import ADD_NEW_TAG
from tag.tests.queries import GET_TAGS_QUERY


def _get_tag_response_collection(response):
    return response['data']['tags']['data']


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_tags_query(graphql_client, graphql_organization):
    tags = create_tags(graphql_organization)

    executed = graphql_client.execute(
        GET_TAGS_QUERY, variables={'searchCriteria': '', 'filter': None}
    )

    collection = _get_tag_response_collection(executed)
    first_result, *_ = collection
    assert len(collection) == 2
    assert int(first_result['id']) == tags[0].id


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_tags_query_get_all_manual(graphql_client, graphql_organization):
    create_tags(graphql_organization)

    executed = graphql_client.execute(
        GET_TAGS_QUERY,
        variables={'searchCriteria': '', 'filter': json.dumps({"manual": True})},
    )

    collection = _get_tag_response_collection(executed)
    first_result, *_ = collection
    assert len(collection) == 1


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_tags_query_search_by_name(graphql_client, graphql_organization):
    tags = create_tags(graphql_organization)

    executed = graphql_client.execute(
        GET_TAGS_QUERY, variables={'searchCriteria': 'first', 'filter': None}
    )

    collection = _get_tag_response_collection(executed)
    first_result, *_ = collection
    assert len(collection) == 1
    assert first_result['name'] == tags[0].name


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_add_new_tag(graphql_client, graphql_organization):
    tag_name = 'New Manual Tag'
    executed = graphql_client.execute(
        ADD_NEW_TAG, variables={'input': dict(name=tag_name, isManual=True)}
    )

    assert executed['data']['addManualTag']['tagId'] is not None
    assert len(Tag.objects.all()) == 1
    assert Tag.objects.all()[0].name == tag_name


@pytest.mark.functional(permissions=['drive.view_driveevidence', 'user.view_concierge'])
def test_add_new_tag_but_name_already_exists(graphql_client, graphql_organization):
    create_tags(graphql_organization)
    tag_name = 'First Tag'

    executed = graphql_client.execute(
        ADD_NEW_TAG, variables={'input': dict(name=tag_name, isManual=True)}
    )

    assert executed['data']['addManualTag']['tagId'] is None
    assert len(Tag.objects.all()) == 2
    assert Tag.objects.all()[0].name == tag_name


def create_tags(organization):
    tags = [
        Tag.objects.create(name='First Tag', organization=organization),
        Tag.objects.create(
            name='Second Tag', organization=organization, is_manual=True
        ),
    ]

    return tags
