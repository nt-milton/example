import pytest
from django.core.files import File
from django.core.files.uploadedfile import SimpleUploadedFile

from action_item.models import ActionItemStatus
from control.models import ControlPillar
from control.tests.factory import create_control
from feature.constants import new_controls_feature_flag, playbooks_feature_flag
from feature.models import Flag
from policy.constants import EMPTY_STRING
from policy.models import Policy
from policy.utils.utils import create_policy_action_items_by_users
from tag.models import Tag
from user.tests import create_user

from .factory import create_empty_policy, create_published_empty_policy
from .mutations import UPDATE_NEW_POLICY, UPDATE_POLICY
from .queries import GET_POLICY_CONTROLS

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


@pytest.fixture(name='_pillar')
def fixture_pillar():
    return ControlPillar.objects.create(name='HR Governance')


@pytest.fixture
def empty_policy(graphql_organization, graphql_user, _pillar):
    return create_empty_policy(
        name='Policy name',
        organization=graphql_organization,
        user=graphql_user,
        is_visible_in_dataroom=False,
        is_required=False,
        control_family=_pillar,
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
        organization=graphql_organization, user=graphql_user, is_published=True
    )


@pytest.fixture()
def second_user(graphql_organization):
    return create_user(
        organization=graphql_organization,
        first_name='Test User Change',
        email='user2@heylaika.com',
    )


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_new_update_policy(
    graphql_client, graphql_organization, graphql_user, second_user
):
    """
    Check that the new mutation works for updating the owner and approver
    of a policy.
    """
    policy = create_empty_policy(graphql_organization, graphql_user)
    updated_policy = graphql_client.execute(
        UPDATE_NEW_POLICY,
        variables={
            "input": {
                "id": policy.id,
                "owner": second_user.email,
                "approver": graphql_user.email,
            }
        },
    )
    approver = updated_policy['data']['updateNewPolicy']['policy']['approver']
    assert (
        second_user.email
        == updated_policy['data']['updateNewPolicy']['policy']['owner']['email']
    )
    assert graphql_user.email == approver['email']


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_delete_null_policy_owner(graphql_client, graphql_organization, graphql_user):
    """
    Check that the new mutation works for deleting the owner
    of a policy when the owner is 'None'
    """
    policy = create_empty_policy(graphql_organization, graphql_user)
    new_policy = graphql_client.execute(
        UPDATE_NEW_POLICY, variables={"input": {"id": policy.id, "owner": None}}
    )
    assert new_policy['data']['updateNewPolicy']['policy']['owner'] is None


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_delete_empty_policy_owner(graphql_client, graphql_organization, graphql_user):
    """
    Check that the new mutation works for deleting the owner
    of a policy when the owner is an empty string
    """
    policy = create_empty_policy(graphql_organization, graphql_user)
    new_policy = graphql_client.execute(
        UPDATE_NEW_POLICY, variables={"input": {"id": policy.id, "owner": ''}}
    )
    assert new_policy['data']['updateNewPolicy']['policy']['owner'] is None


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_policy_mutation_does_not_change_owner(
    graphql_client, graphql_organization, graphql_user
):
    """
    Check that the new update policy mutation does not do anything
    if the owner is not provided in the input
    """
    policy = create_empty_policy(graphql_organization, graphql_user)
    new_policy = graphql_client.execute(
        UPDATE_NEW_POLICY, variables={"input": {"id": policy.id}}
    )
    assert (
        graphql_user.email
        == new_policy['data']['updateNewPolicy']['policy']['owner']['email']
    )


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_policy_mutation_does_not_change_approver(
    graphql_client, graphql_organization, graphql_user
):
    """
    Check that the new update policy mutation does not do anything
    if the approver is not provided in the input
    """
    policy = create_empty_policy(graphql_organization, graphql_user)
    new_policy = graphql_client.execute(
        UPDATE_NEW_POLICY, variables={"input": {"id": policy.id}}
    )
    assert (
        graphql_user.email
        == new_policy['data']['updateNewPolicy']['policy']['approver']['email']
    )


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_new_update_policy_approver(
    graphql_client, graphql_organization, graphql_user, second_user
):
    policy = create_empty_policy(graphql_organization, graphql_user)
    updated_policy = graphql_client.execute(
        UPDATE_NEW_POLICY,
        variables={"input": {"id": policy.id, "approver": second_user.email}},
    )
    approver = updated_policy['data']['updateNewPolicy']['policy']['approver']
    assert second_user.email == approver['email']


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_delete_null_policy_approver(
    graphql_client, graphql_organization, graphql_user
):
    policy = create_empty_policy(graphql_organization, graphql_user)
    new_policy = graphql_client.execute(
        UPDATE_NEW_POLICY, variables={"input": {"id": policy.id, "approver": None}}
    )
    assert new_policy['data']['updateNewPolicy']['policy']['approver'] is None


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_delete_empty_policy_approver(
    graphql_client, graphql_organization, graphql_user
):
    policy = create_empty_policy(graphql_organization, graphql_user)
    new_policy = graphql_client.execute(
        UPDATE_NEW_POLICY, variables={"input": {"id": policy.id, "approver": ''}}
    )
    assert new_policy['data']['updateNewPolicy']['policy']['approver'] is None


@pytest.mark.functional(permissions=['policy.view_policy'])
def test_resolve_policy_message_data_controls(
    graphql_client, graphql_organization, empty_policy, _pillar
):
    control_1 = create_control(graphql_organization, 1, 'control 1', pillar=_pillar)
    control_2 = create_control(graphql_organization, 1, 'control 2', pillar=_pillar)

    policy_data = graphql_client.execute(
        GET_POLICY_CONTROLS, variables={'id': str(empty_policy.id)}
    )

    controls = policy_data['data']['policy']['data']['controls']
    controls_ids = {control['id'] for control in controls}
    assert controls_ids == {str(control_1.id), str(control_2.id)}


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_update_policy_name(
    graphql_client, graphql_organization, graphql_user, second_user, empty_policy
):
    new_name = 'New policy name'
    graphql_client.execute(
        UPDATE_NEW_POLICY,
        variables={"input": {"id": empty_policy.id, "name": new_name}},
    )
    assert Policy.objects.get(id=empty_policy.id).name == new_name


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_not_delete_policy_name_if_empty_string(
    graphql_client, graphql_organization, graphql_user, second_user, empty_policy
):
    graphql_client.execute(
        UPDATE_NEW_POLICY, variables={"input": {"id": empty_policy.id, "name": ''}}
    )
    assert Policy.objects.get(id=empty_policy.id).name == 'Policy name'


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_not_delete_policy_name_if_none(
    graphql_client, graphql_organization, graphql_user, second_user, empty_policy
):
    graphql_client.execute(
        UPDATE_NEW_POLICY, variables={"input": {"id": empty_policy.id, "name": None}}
    )
    assert Policy.objects.get(id=empty_policy.id).name == 'Policy name'


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_update_policy_description(
    graphql_client, graphql_organization, graphql_user, second_user, empty_policy
):
    new_description = 'New policy description'
    graphql_client.execute(
        UPDATE_NEW_POLICY,
        variables={"input": {"id": empty_policy.id, "description": new_description}},
    )
    policy = Policy.objects.get(id=empty_policy.id)
    assert policy.description == new_description


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_delete_policy_description_with_empty_string(
    graphql_client, graphql_organization, graphql_user, second_user, empty_policy
):
    graphql_client.execute(
        UPDATE_NEW_POLICY,
        variables={"input": {"id": empty_policy.id, "description": EMPTY_STRING}},
    )
    policy = Policy.objects.get(id=empty_policy.id)
    assert policy.description == EMPTY_STRING


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_delete_policy_description_with_none(
    graphql_client, graphql_organization, graphql_user, second_user, empty_policy
):
    graphql_client.execute(
        UPDATE_NEW_POLICY,
        variables={"input": {"id": empty_policy.id, "description": None}},
    )
    policy = Policy.objects.get(id=empty_policy.id)
    assert policy.description == EMPTY_STRING


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_update_tags(
    graphql_client,
    graphql_organization,
    graphql_user,
    second_user,
    empty_policy,
    _organization_tags,
):
    tags = [
        {'id': '1', 'name': 'tag 1'},
        {'id': '3', 'name': 'tag 3'},
        {'id': None, 'name': 'tag 4'},
    ]
    graphql_client.execute(
        UPDATE_NEW_POLICY, variables={"input": {"id": empty_policy.id, "tags": tags}}
    )
    policy = Policy.objects.get(id=empty_policy.id)
    tags_names_set = {tag.name for tag in policy.tags.all()}
    assert tags_names_set == {'tag 1', 'tag 3', 'tag 4'}


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_delete_tags_with_empty_list(
    graphql_client,
    graphql_organization,
    graphql_user,
    second_user,
    empty_policy,
    _organization_tags,
):
    empty_policy.tags.add(*_organization_tags)
    graphql_client.execute(
        UPDATE_NEW_POLICY, variables={"input": {"id": empty_policy.id, "tags": []}}
    )
    policy = Policy.objects.get(id=empty_policy.id)
    assert policy.tags.count() == 0


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_delete_tags_with_none(
    graphql_client,
    graphql_organization,
    graphql_user,
    second_user,
    empty_policy,
    _organization_tags,
):
    empty_policy.tags.add(*_organization_tags)
    graphql_client.execute(
        UPDATE_NEW_POLICY, variables={"input": {"id": empty_policy.id, "tags": None}}
    )
    policy = Policy.objects.get(id=empty_policy.id)
    assert policy.tags.count() == 0


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_update_is_required(
    graphql_client, graphql_organization, graphql_user, second_user, empty_policy
):
    graphql_client.execute(
        UPDATE_NEW_POLICY,
        variables={"input": {"id": empty_policy.id, "isRequired": True}},
    )
    policy = Policy.objects.get(id=empty_policy.id)
    assert policy.is_required is True


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_update_is_visible_in_dataroom(
    graphql_client, graphql_organization, graphql_user, second_user, empty_policy
):
    graphql_client.execute(
        UPDATE_NEW_POLICY,
        variables={"input": {"id": empty_policy.id, "isVisibleInDataroom": True}},
    )
    policy = Policy.objects.get(id=empty_policy.id)
    assert policy.is_visible_in_dataroom is True


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_delete_uncompleted_action_items_for_not_required_policy(
    graphql_client, graphql_user, second_user, published_empty_policy
):
    create_policy_action_items_by_users(
        [graphql_user, second_user], published_empty_policy
    )
    action_item = published_empty_policy.action_items.first()
    action_item.status = ActionItemStatus.COMPLETED
    action_item.save()
    graphql_client.execute(
        UPDATE_POLICY,
        variables={
            "id": str(published_empty_policy.id),
            "input": {
                "administratorEmail": graphql_user.email,
                "approverEmail": graphql_user.email,
                "ownerEmail": graphql_user.email,
                "category": published_empty_policy.category,
                "description": published_empty_policy.description,
                "isRequired": False,
                "isVisibleInDataroom": True,
                "name": published_empty_policy.name,
                "tags": [],
            },
        },
    )
    policy = Policy.objects.get(id=published_empty_policy.id)
    assert policy.is_required is False
    assert policy.action_items.count() == 1


@pytest.mark.functional(permissions=['policy.change_policy'])
def test_create_action_items_for_required_policy(
    graphql_client, graphql_user, second_user, published_empty_policy
):
    create_policy_action_items_by_users([graphql_user], published_empty_policy)
    graphql_client.execute(
        UPDATE_POLICY,
        variables={
            "id": str(published_empty_policy.id),
            "input": {
                "administratorEmail": graphql_user.email,
                "approverEmail": graphql_user.email,
                "ownerEmail": graphql_user.email,
                "category": published_empty_policy.category,
                "description": published_empty_policy.description,
                "isRequired": True,
                "isVisibleInDataroom": True,
                "name": published_empty_policy.name,
                "tags": [],
            },
        },
    )
    policy = Policy.objects.get(id=published_empty_policy.id)
    assert policy.is_required is True
    assert policy.action_items.count() == 2
