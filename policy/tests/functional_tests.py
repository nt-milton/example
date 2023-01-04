import base64
import json
import os
from unittest.mock import patch

import pytest
from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Q

from action_item.constants import TYPE_POLICY
from action_item.models import ActionItem
from control.tests.factory import create_control_pillar
from feature.constants import new_controls_feature_flag, playbooks_feature_flag
from feature.models import Flag
from laika.utils.exceptions import ServiceException
from policy.constants import (
    BAD_FORMATTED_DOCX_DRAFT_FILE_EXCEPTION_MSG,
    INCOMPATIBLE_DRAFT_FILE_FORMAT_EXCEPTION_MSG,
)
from policy.docx_helper import get_validated_docx_file, remove_proposed_changes
from policy.errors import (
    BAD_FORMATTED_DOCX_FILE_ERROR,
    MISSING_POLICY_OWNER_ERROR,
    WRONG_DRAFT_FILE_FORMAT_ERROR,
)
from policy.helpers import get_publish_policy_error_message
from policy.models import Policy, PublishedPolicy
from policy.views import get_published_policy_pdf
from tag.models import Tag
from user.models import User

from .factory import create_empty_policy, create_published_empty_policy
from .mutations import (
    BATCH_DELETE_POLICIES,
    CREATE_POLICY_OR_PROCEDURE,
    DELETE_POLICY,
    PUBLISH_POLICY,
    REPLACE_POLICY,
    UNPUBLISH_POLICY,
    UPDATE_IS_DRAFT_EDITED,
)
from .queries import (
    GET_FILTERED_POLICIES,
    GET_POLICIES_QUERY,
    GET_POLICY_FILTERS,
    GET_PUBLISHED_POLICIES,
)

EXPORT_DOCUMENT_PATH = 'policy.views.export_document_bytes'
MERGE_PATH = 'policy.views.merge'
RENDER_TEMPLATE_TO_PDF_PATH = 'policy.views.render_template_to_pdf'


@pytest.fixture(name='_organization_tags')
def fixture_organization_tags(graphql_organization):
    tag_1 = Tag.objects.create(
        name='tag 1', organization=graphql_organization, is_manual=True
    )
    tag_2 = Tag.objects.create(
        name='tag 2',
        organization=graphql_organization,
    )
    return tag_1, tag_2


@pytest.fixture(name='_control_family_enabled')
def control_family_enabled(graphql_organization):
    Flag.objects.get_or_create(
        name=new_controls_feature_flag,
        organization=graphql_organization,
        defaults={'is_enabled': True},
    )
    Flag.objects.get_or_create(
        name=playbooks_feature_flag,
        organization=graphql_organization,
        defaults={'is_enabled': False},
    )


@pytest.fixture
def empty_policy(graphql_organization, graphql_user):
    return create_empty_policy(
        name='Policy name',
        organization=graphql_organization,
        user=graphql_user,
        is_visible_in_dataroom=False,
        is_required=False,
    )


@pytest.fixture(name='_policy_with_wrong_file_format')
def policy_with_wrong_file_format(graphql_organization, graphql_user):
    policy_with_pdf_file_as_draft = File(
        file=SimpleUploadedFile('some_file_name.pdf', b'Test pdf file'),
        name='some_file_name.pdf',
    )
    empty_policy = create_empty_policy(graphql_organization, graphql_user)
    empty_policy.draft = policy_with_pdf_file_as_draft
    empty_policy.save()
    return empty_policy


@pytest.fixture(name='_policy_with_corrupt_docx_file')
def policy_with_corrupt_docx_file(graphql_organization, graphql_user):
    corrupt_empty_file = open('policy/assets/corrupt_empty.docx', 'rb')
    docx = File(name='corrupt_empty.docx', file=corrupt_empty_file)
    empty_policy = create_empty_policy(graphql_organization, graphql_user)
    empty_policy.draft = docx
    empty_policy.save()
    return empty_policy


@pytest.fixture
def published_empty_policy(graphql_organization, graphql_user):
    return create_published_empty_policy(
        organization=graphql_organization, user=graphql_user
    )


@pytest.mark.functional(permissions=['policy.publish_policy'])
def test_policies_query(graphql_client, graphql_organization, empty_policy):
    publish_input = {
        'input': dict(policyId=empty_policy.id, comment='Publishing empty')
    }
    publish_input_2 = {'input': dict(policyId=2, comment='Publishing empty 2')}

    graphql_client.execute(PUBLISH_POLICY, variables=publish_input)
    graphql_client.execute(PUBLISH_POLICY, variables=publish_input_2)
    executed = graphql_client.execute(
        GET_POLICIES_QUERY,
        variables={'orderBy': json.dumps({"field": "name", "order": "ascend"})},
    )

    policies = Policy.objects.all()

    assert executed
    assert policies[0] == empty_policy


@pytest.mark.functional(permissions=['policy.publish_policy'])
def test_approved_owned_by_population_when_publish_policy(
    graphql_client, graphql_organization, empty_policy
):
    publish_input = {
        'input': dict(policyId=empty_policy.id, comment='Publishing empty')
    }

    graphql_client.execute(PUBLISH_POLICY, variables=publish_input)

    policy = Policy.objects.all().first()

    published_policy = PublishedPolicy.objects.all().first()

    assert published_policy.owned_by.id == policy.owner.id
    assert published_policy.approved_by.id == policy.approver.id


@pytest.mark.functional
def test_policies_query_no_order(graphql_client, graphql_organization, empty_policy):
    publish_input_test = {'input': dict(policyId=4, comment='Publishing empty test')}

    graphql_client.execute(PUBLISH_POLICY, variables=publish_input_test)
    executed = graphql_client.execute(GET_POLICIES_QUERY)
    policies = Policy.objects.all()

    assert executed
    assert policies[0] == empty_policy


@pytest.mark.functional(permissions=['policy.publish_policy'])
def test_publish_policy_is_required(graphql_client, graphql_organization, empty_policy):
    empty_policy.is_required = True
    empty_policy.save()
    publish_input_test = {
        'input': dict(policyId=empty_policy.id, comment='Publishing empty test')
    }

    executed = graphql_client.execute(PUBLISH_POLICY, variables=publish_input_test)
    users = User.objects.filter(organization=graphql_organization).count()
    assert executed['data']['publishPolicy']['data']['isPublished'] is True
    assert users == ActionItem.objects.count()
    assert Policy.objects.get(id=empty_policy.id).action_items.count() == users


@pytest.mark.functional(permissions=['policy.publish_policy', 'policy.delete_policy'])
def test_delete_policy_published_is_required(
    graphql_client, graphql_organization, empty_policy
):
    empty_policy.is_required = True
    empty_policy.save()
    publish_input_test = {
        'input': dict(policyId=empty_policy.id, comment='Publishing empty test')
    }

    # Create the actions items
    graphql_client.execute(PUBLISH_POLICY, variables=publish_input_test)

    users = User.objects.filter(organization=graphql_organization)
    assert Policy.objects.get(id=empty_policy.id).action_items.count() == len(users)

    # Check if the column is False once the policy has been published
    for user in users:
        assert user.policies_reviewed is False

    executed = graphql_client.execute(
        DELETE_POLICY, variables={'id': str(empty_policy.id)}
    )
    assert executed['data']['deletePolicy']['success'] is True
    assert ActionItem.objects.filter(metadata__type=TYPE_POLICY).count() == 0

    # Check if the column is True once the policy has been removed
    for user in User.objects.filter(organization=graphql_organization):
        assert user.policies_reviewed is True


@pytest.mark.functional(
    permissions=['policy.publish_policy', 'policy.batch_delete_policy']
)
def test_batch_delete_policy_published_is_required(
    graphql_client, graphql_organization, graphql_user
):
    policies = []
    users = User.objects.filter(organization=graphql_organization).count()
    for _ in range(2):
        policy = create_empty_policy(
            graphql_organization, graphql_user, **{'is_required': True}
        )
        publish_input_test = {
            'input': dict(policyId=policy.id, comment='Publishing empty test')
        }
        policies.append(str(policy.id))

        # Create the actions items
        graphql_client.execute(PUBLISH_POLICY, variables=publish_input_test)
        assert Policy.objects.get(id=policy.id).action_items.count() == users

    # Check if the column is False once the policy has been published
    for user in User.objects.filter(organization=graphql_organization):
        assert user.policies_reviewed is False

    executed = graphql_client.execute(
        BATCH_DELETE_POLICIES, variables={'policyIds': policies}
    )
    assert executed['data']['deletePolicies']['success'] is True
    assert ActionItem.objects.filter(metadata__type=TYPE_POLICY).count() == 0

    # Check if the column is True once the policy has been removed
    for user in User.objects.filter(organization=graphql_organization):
        assert user.policies_reviewed is True


@pytest.mark.functional(permissions=['policy.publish_policy'])
def test_publish_policy_is_required_already_published(
    graphql_client, graphql_organization, published_empty_policy
):
    """
    When the policy is re-published the actions items shouldn't be created
    again.
    """
    published_empty_policy.is_required = True
    published_empty_policy.save()
    publish_input_test = {
        'input': dict(
            policyId=published_empty_policy.id, comment='Publishing empty test'
        )
    }
    with patch(
        'policy.schema.update_action_items_by_policy'
    ) as update_action_items_by_policy:
        update_action_items_by_policy.return_value = ''
        executed = graphql_client.execute(PUBLISH_POLICY, variables=publish_input_test)
        policy = Policy.objects.get(id=published_empty_policy.id)
        assert policy.action_items.count() == 0
        assert executed['data']['publishPolicy']['data']['isPublished'] is True
        update_action_items_by_policy.assert_called()


@pytest.mark.functional(permissions=['policy.publish_policy'])
def test_policy_updated_at_on_publish_(
    graphql_client, graphql_organization, empty_policy
):
    publish_input = {
        'input': dict(policyId=empty_policy.id, comment='Publishing empty')
    }

    policy_updated_at = empty_policy.updated_at

    graphql_client.execute(PUBLISH_POLICY, variables=publish_input)

    published_policy = Policy.objects.get(
        id=empty_policy.id, organization=graphql_organization
    )
    published_policy_updated_at = published_policy.updated_at
    assert policy_updated_at < published_policy_updated_at


@pytest.mark.functional(permissions=['policy.unpublish_policy'])
def test_policy_updated_at_on_unpublish(
    graphql_client, graphql_organization, published_empty_policy
):
    published_policy_updated_at = published_empty_policy.updated_at

    unpublish_input = {'input': dict(policyId=published_empty_policy.id)}

    graphql_client.execute(UNPUBLISH_POLICY, variables=unpublish_input)

    unpublished_policy = Policy.objects.get(
        id=published_empty_policy.id, organization=graphql_organization
    )

    assert published_policy_updated_at < unpublished_policy.updated_at


@pytest.mark.functional(permissions=['policy.publish_policy'])
@patch(EXPORT_DOCUMENT_PATH)
@patch(MERGE_PATH, return_value=True)
@patch(RENDER_TEMPLATE_TO_PDF_PATH)
def test_get_published_policy_pdf(
    mock_render_pdf, mock_merge, mock_export_document, published_empty_policy
):
    published_policy = published_empty_policy.versions.first()
    latest_version = PublishedPolicy.objects.create(
        published_by=published_policy.published_by,
        owned_by=published_policy.owned_by,
        approved_by=published_policy.approved_by,
        policy=published_empty_policy,
        contents=published_policy.contents,
        comment='published',
    )
    get_published_policy_pdf(published_empty_policy.id)
    assert latest_version.published_key is not published_policy.published_key
    assert mock_export_document.called is True
    mock_export_document.assert_called_with(
        latest_version.published_key,
        latest_version.policy.name,
        latest_version.contents.url,
    )
    assert mock_render_pdf.called is True
    call_args, call_kwargs = mock_render_pdf.call_args
    assert call_kwargs['context']['published_policy'] == latest_version
    assert mock_merge.called is True


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_update_is_draft_edited(graphql_client, graphql_organization, empty_policy):
    executed = graphql_client.execute(
        UPDATE_IS_DRAFT_EDITED, variables={'input': dict(id=str(empty_policy.id))}
    )

    response = executed['data']
    policy = graphql_organization.policies.all().first()

    assert response['updateIsDrafEdited']['success'] is True
    assert policy.is_draft_edited is True


@pytest.mark.parametrize('dataroom_only, total', [(True, 1), (False, 2)])
@pytest.mark.functional
def test_published_policies(
    dataroom_only, total, graphql_client, graphql_organization, graphql_user
):
    general_policy = create_published_empty_policy(
        organization=graphql_organization, user=graphql_user
    )
    general_policy.is_published = True
    general_policy.save()

    dataroom_policy = create_published_empty_policy(
        organization=graphql_organization, user=graphql_user
    )
    dataroom_policy.is_visible_in_dataroom = False
    dataroom_policy.is_published = True
    dataroom_policy.save()

    response = graphql_client.execute(
        GET_PUBLISHED_POLICIES, variables={'dataroomOnly': dataroom_only}
    )

    policies = response['data']['publishedPolicies']['data']
    assert len(policies) is total


@pytest.mark.functional(permissions=['policy.add_policy'])
def test_create_policy(graphql_client):
    response = graphql_client.execute(
        CREATE_POLICY_OR_PROCEDURE,
        variables={
            'input': dict(
                name='Test Name 1',
                category='Business Continuity & Disaster Recovery',
                description='Test description 1',
                policyType='Policy',
                isRequired=True,
            )
        },
    )

    policy_type = response['data']['createPolicy']['data']['policyType']
    policy_name = response['data']['createPolicy']['data']['name']

    assert policy_type == 'Policy'
    assert policy_name == 'Test Name 1'


@pytest.mark.functional(permissions=['policy.add_policy'])
def test_create_procedure(graphql_client):
    response = graphql_client.execute(
        CREATE_POLICY_OR_PROCEDURE,
        variables={
            'input': dict(
                name='Test Name 2',
                category='Business Continuity',
                description='Test description 2',
                policyType='Procedure',
                isRequired=False,
            )
        },
    )

    policy_type = response['data']['createPolicy']['data']['policyType']
    policy_name = response['data']['createPolicy']['data']['name']

    assert policy_type == 'Procedure'
    assert policy_name == 'Test Name 2'


@pytest.mark.functional(permissions=['policy.view_policy'])
@patch('policy.schema.Q')
def test_get_policies_query_with_owners_filter(
    mocked_q, graphql_client, graphql_organization, graphql_user
):
    # Mocking Q instance because UNACCENT function is not supported in sqlite.
    # When testing the Search filter consider mocking the return value as
    # Q(name__icontains=$input_for_search_filter) instead of Q()
    mocked_q.return_value = Q()
    create_empty_policy(graphql_organization, graphql_user)
    create_empty_policy(graphql_organization, None)
    unassigned_owner = "0"
    executed = graphql_client.execute(
        GET_FILTERED_POLICIES,
        variables={
            "filters": {"owner": [unassigned_owner]},
            "pageSize": 50,
            "page": 1,
            "orderBy": {"field": "display_id", "order": "ascend"},
        },
    )

    policies = Policy.objects.all()
    response = executed['data']['filteredPolicies']['data']

    assert len(response) == 1
    assert response[0]['owner'] is None
    assert len(policies) == 2


@pytest.mark.functional(permissions=['policy.view_policy'])
@patch('policy.schema.Q')
def test_get_filtered_policies_with_type_filter(
    mocked_q, graphql_client, graphql_organization, graphql_user
):
    # Mocking Q instance because UNACCENT function is not supported in sqlite.
    # When testing the Search filter consider mocking the return value as
    # Q(name__icontains=$input_for_search_filter) instead of Q()
    mocked_q.return_value = Q()
    create_empty_policy(
        graphql_organization, graphql_user, name='Asset Inventory Policy'
    )
    create_empty_policy(
        graphql_organization,
        graphql_user,
        name='Procedure Test',
        policy_type='Procedure',
    )
    response = graphql_client.execute(
        GET_FILTERED_POLICIES, variables={"filters": {"type": ["Procedure"]}, "page": 1}
    )['data']['filteredPolicies']['data']

    assert len(response) == 1
    assert response[0]['name'] == 'Procedure Test'
    assert response[0]['policyType'] == 'Procedure'


@pytest.mark.functional(permissions=['policy.view_policy'])
@patch('policy.schema.Q')
def test_get_filtered_policies_with_control_family_filter(
    mocked_q, graphql_client, graphql_organization, graphql_user
):
    # Mocking Q instance because UNACCENT function is not supported in sqlite.
    # When testing the Search filter consider mocking the return value as
    # Q(name__icontains=$input_for_search_filter) instead of Q()
    mocked_q.return_value = Q()
    control_family_1 = create_control_pillar('Control Family 1')
    create_empty_policy(
        graphql_organization,
        graphql_user,
        name='Asset Inventory Policy',
        control_family=control_family_1,
    )
    create_empty_policy(
        graphql_organization,
        graphql_user,
        name='Procedure Test',
        policy_type='Procedure',
    )
    response = graphql_client.execute(
        GET_FILTERED_POLICIES,
        variables={"filters": {"controlFamily": [control_family_1.id]}, "page": 1},
    )['data']['filteredPolicies']['data']

    assert len(response) == 1
    assert response[0]['name'] == 'Asset Inventory Policy'
    assert response[0]['controlFamily']['name'] == 'Control Family 1'


@pytest.mark.functional(permissions=['policy.view_policy'])
@patch('policy.schema.Q')
def test_get_filtered_policies_with_category_filter(
    mocked_q, graphql_client, graphql_organization, graphql_user
):
    # Mocking Q instance because UNACCENT function is not supported in sqlite.
    # When testing the Search filter consider mocking the return value as
    # Q(name__icontains=$input_for_search_filter) instead of Q()
    mocked_q.return_value = Q()
    create_empty_policy(
        graphql_organization, graphql_user, name='Asset Inventory Policy'
    )
    create_empty_policy(
        graphql_organization,
        graphql_user,
        name='Access Control Policy',
        policy_type='Procedure',
        category='Configuration Management',
    )
    response = graphql_client.execute(
        GET_FILTERED_POLICIES,
        variables={'filters': {'category': ['Configuration Management']}, "page": 1},
    )['data']['filteredPolicies']['data']

    assert len(response) == 1
    assert response[0]['name'] == 'Access Control Policy'
    assert response[0]['category'] == 'Configuration Management'


@pytest.mark.functional(permissions=['policy.view_policy'])
@patch('policy.schema.Q')
def test_get_filtered_policies_with_published_status_filter(
    mocked_q, graphql_client, graphql_organization, graphql_user
):
    # Mocking Q instance because UNACCENT function is not supported in sqlite.
    # When testing the Search filter consider mocking the return value as
    # Q(name__icontains=$input_for_search_filter) instead of Q()
    mocked_q.return_value = Q()
    create_empty_policy(
        graphql_organization, graphql_user, name='Asset Inventory Policy'
    )
    published_policy = create_published_empty_policy(
        graphql_organization, graphql_user, name='Access Control Policy'
    )
    published_policy.is_published = True
    published_policy.save()

    response = graphql_client.execute(
        GET_FILTERED_POLICIES,
        variables={'filters': {'isPublished': ['published']}, "page": 1},
    )['data']['filteredPolicies']['data']

    assert len(response) == 1
    assert response[0]['name'] == 'Access Control Policy'
    assert response[0]['isPublished'] is True


@pytest.mark.functional(permissions=['policy.view_policy'])
@patch('policy.schema.Q')
def test_get_filtered_policies_with_tags_filter(
    mocked_q, graphql_client, graphql_organization, graphql_user
):
    # Mocking Q instance because UNACCENT function is not supported in sqlite.
    # When testing the Search filter consider mocking the return value as
    # Q(name__icontains=$input_for_search_filter) instead of Q()
    mocked_q.return_value = Q()
    tag_1 = Tag.objects.create(name='Tag 1', organization=graphql_organization)
    create_empty_policy(graphql_organization, graphql_user)
    policy_1 = create_empty_policy(
        graphql_organization, graphql_user, name='Access Control Policy', display_id=1
    )
    policy_2 = create_empty_policy(
        graphql_organization, graphql_user, name='Asset Inventory Policy', display_id=2
    )

    policy_1.tags.add(tag_1)
    policy_2.tags.add(tag_1)

    response = graphql_client.execute(
        GET_FILTERED_POLICIES, variables={'filters': {'tags': [tag_1.id]}, "page": 1}
    )['data']['filteredPolicies']['data']

    policy_1_from_response = response[0]
    policy_2_from_response = response[1]

    assert len(response) == 2
    assert policy_1_from_response['name'] == 'Access Control Policy'
    assert policy_2_from_response['name'] == 'Asset Inventory Policy'
    assert policy_1_from_response['tags'][0] == 'Tag 1'
    assert policy_2_from_response['tags'][0] == 'Tag 1'


@pytest.mark.functional()
def test_get_policy_filters(
    _control_family_enabled, graphql_client, graphql_organization
):
    user_1 = User.objects.create(
        organization=graphql_organization,
        first_name='User 1',
        email='user1@heylaika.com',
    )
    tag_1 = Tag.objects.create(name='Tag 1', organization=graphql_organization)
    tag_2 = Tag.objects.create(name='Tag 2', organization=graphql_organization)
    control_family_1 = create_control_pillar('Control Family 1')
    control_family_2 = create_control_pillar('Control Family 2')
    policy_1 = create_empty_policy(
        graphql_organization,
        None,
        name='Access Control Policy',
        control_family=control_family_1,
    )
    policy_2 = create_empty_policy(
        graphql_organization,
        user_1,
        name='Asset Inventory Policy',
        control_family=control_family_2,
    )

    policy_1.tags.add(tag_1)
    policy_2.tags.add(tag_2)

    response = graphql_client.execute(GET_POLICY_FILTERS)['data']['policyFilters']

    owners = response[0]
    type = response[1]
    control_family = response[2]
    published_status = response[3]
    tags = response[4]

    assert owners['items'][0]['name'] == 'User 1'
    assert type['items'][0]['name'] == 'Policy'
    assert type['items'][1]['name'] == 'Procedure'
    assert control_family['items'][0]['name'] == 'Control Family 1'
    assert control_family['items'][1]['name'] == 'Control Family 2'
    assert published_status['items'][0]['name'] == 'Published'
    assert published_status['items'][1]['name'] == 'Not Published'
    assert tags['items'][0]['name'] == 'Tag 1'
    assert tags['items'][1]['name'] == 'Tag 2'


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_replace_policy_with_not_docx_file(
    _policy_with_wrong_file_format, graphql_client
):
    encoded_draft_file = base64.b64encode(
        _policy_with_wrong_file_format.draft.read()
    ).decode('UTF-8')
    response = graphql_client.execute(
        REPLACE_POLICY,
        variables={
            'input': dict(
                id=str(_policy_with_wrong_file_format.id),
                draft={
                    'fileName': os.path.basename(
                        _policy_with_wrong_file_format.draft.name
                    ),
                    'file': encoded_draft_file,
                },
            )
        },
    )
    assert (
        response['errors'][0]['message'] == INCOMPATIBLE_DRAFT_FILE_FORMAT_EXCEPTION_MSG
    )


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_replace_policy_with_corrupt_docx_file(
    _policy_with_corrupt_docx_file, graphql_client
):
    encoded_draft_file = base64.b64encode(
        _policy_with_corrupt_docx_file.draft.read()
    ).decode('UTF-8')
    response = graphql_client.execute(
        REPLACE_POLICY,
        variables={
            'input': dict(
                id=str(_policy_with_corrupt_docx_file.id),
                draft={
                    'fileName': os.path.basename(
                        _policy_with_corrupt_docx_file.draft.name
                    ),
                    'file': encoded_draft_file,
                },
            )
        },
    )
    assert (
        response['errors'][0]['message'] == BAD_FORMATTED_DOCX_DRAFT_FILE_EXCEPTION_MSG
    )


@pytest.mark.functional()
def test_remove_proposed_changes_with_corrupt_docx(_policy_with_corrupt_docx_file):
    with pytest.raises(
        ServiceException, match=BAD_FORMATTED_DOCX_DRAFT_FILE_EXCEPTION_MSG
    ):
        remove_proposed_changes(
            _policy_with_corrupt_docx_file.draft, _policy_with_corrupt_docx_file.id
        )


@pytest.mark.functional()
def test_get_validated_docx_file_from_policy_with_not_docx_file(
    _policy_with_wrong_file_format,
):
    with pytest.raises(
        ServiceException, match=INCOMPATIBLE_DRAFT_FILE_FORMAT_EXCEPTION_MSG
    ):
        get_validated_docx_file(_policy_with_wrong_file_format)


@pytest.mark.functional()
def test_get_publish_policy_error_message():
    assert (
        get_publish_policy_error_message('MissingPolicyOAA')
        == MISSING_POLICY_OWNER_ERROR
    )
    assert (
        get_publish_policy_error_message(INCOMPATIBLE_DRAFT_FILE_FORMAT_EXCEPTION_MSG)
        == WRONG_DRAFT_FILE_FORMAT_ERROR
    )
    assert (
        get_publish_policy_error_message(BAD_FORMATTED_DOCX_DRAFT_FILE_EXCEPTION_MSG)
        == BAD_FORMATTED_DOCX_FILE_ERROR
    )
