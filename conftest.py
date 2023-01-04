import io
import json
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

import jwt
import pytest
from django.contrib.auth.models import Group
from django.core.files import File
from django.core.files.storage import FileSystemStorage
from django.test import Client as DjangoClient
from django.test import override_settings
from graphene import Context
from graphene.test import Client

from access_review.models import (
    AccessReview,
    AccessReviewObject,
    AccessReviewVendor,
    AccessReviewVendorPreference,
)
from action_item.models import ActionItem
from audit.constants import AUDIT_FIRMS
from audit.tests.factory import create_audit_firm
from comment.constants import RESOLVED
from comment.models import Comment, Reply
from evidence.constants import FILE
from evidence.models import Evidence
from integration.tests.factory import create_connection_account, create_integration
from integration.tests.functional_tests import generate_testing_role
from laika import storage
from laika.auth import (
    AuditAuthenticationBackend,
    AuthenticationBackend,
    ConciergeAuthenticationBackend,
)
from laika.middlewares.LoadersMiddleware import Loaders
from laika.schema import schema
from laika.settings import OKTA_API_KEY
from laika.tests.mock_redis import MockRedis
from monitor import temp_context
from objects.system_types import USER
from objects.tests.factory import create_laika_object, create_object_type
from organization.models import ONBOARDING
from organization.tests import create_organization
from user.constants import AUDITOR_ADMIN
from user.tests import create_user, create_user_auditor
from vendor.tests.factory import create_organization_vendor, create_vendor

pytest_plugins = [
    'audit.tests.fixtures.audits',
    'audit.tests.fixtures.fieldwork_fix',
    'blueprint.tests.fixtures.blueprint',
]

JSON_CONTENT_TYPE = 'application/json'


@pytest.fixture(autouse=True, scope='session')
def redis_connection_mock():
    with patch('laika.utils.redis.get_redis_connection') as redis_conn_mck:
        redis_conn_mck.return_value = MagicMock(wraps=MockRedis())
        yield redis_conn_mck


@pytest.fixture()
def temp_context_runner():
    with patch('monitor.runner._validate_query'), patch(
        'monitor.factory.get_monitor_runner'
    ) as mock:
        mock.return_value = temp_context
        yield


@pytest.fixture(autouse=True, scope='session')
def configure_fake_s3(tmpdir_factory):
    """Configure a fake storage to use temp files instead of S3"""
    tmp_dir = tmpdir_factory.getbasetemp()
    fake = FileSystemStorage(location=tmp_dir)

    def fake_s3(s3_storage):
        s3_storage._save = fake._save
        s3_storage._open = fake._open

    fake_s3(storage.PrivateMediaStorage)
    fake_s3(storage.PublicMediaStorage)
    fake_s3(storage.StaticStorage)


@pytest.fixture(autouse=True, scope='session')
def configure_fake_celery():
    with override_settings(
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_TASK_EAGER_PROPOGATES=True,
        BROKER_URL='memory://',
        CELERY_RESULT_BACKEND="django-db",
        EMAIL_BACKEND='django.core.mail.backends.dummy.EmailBackend',
    ):
        yield


@pytest.fixture(autouse=True, scope='session')
def configure_fake_cloudsearch():
    """Configure a fake cloudsearch client"""
    with patch('search.cloudsearch.cloudsearch.upload_documents'), patch(
        'search.indexing.base_index.BaseIndex.add_index_records_async'
    ), patch('search.indexing.base_index.BaseIndex.remove_index_records_async'), patch(
        'search.cloudsearch.cloudsearch'
    ):
        yield


@pytest.fixture(autouse=True, scope='session')
def configure_fake_openai():
    """Configure a fake openai"""
    with patch('openai.embeddings_utils.get_embedding'), patch(
        'openai.Completion.create'
    ), patch('openai.Embedding.create'):
        yield


def configure_fake_login(user):
    """Avoid cognito calls for testing"""

    def fake_authenticate(backend, context, **kwargs):
        if context:
            context.user = user
            return user

    AuthenticationBackend.authenticate = fake_authenticate
    AuditAuthenticationBackend.authenticate = fake_authenticate
    ConciergeAuthenticationBackend.authenticate = fake_authenticate


@pytest.fixture
def client(request):
    functional_marker = request.node.get_closest_marker("functional")
    if not functional_marker:
        message = '@pytest.mark.functional() required to access Graphql client'
        raise RuntimeError(message)
    return Client(schema)


@pytest.fixture
def graphql_organization(request):
    """Configure a fake org to be used in graphql calls"""
    functional_marker = request.node.get_closest_marker("functional")
    flags = []
    if functional_marker:
        flags = functional_marker.kwargs.get('feature_flags', [])
    return create_organization(flags=flags, name='')


@pytest.fixture
def graphql_audit_firm():
    """Configure a fake audit firm to be used in graphql calls"""
    return create_audit_firm(AUDIT_FIRMS[1])


@pytest.fixture
def graphql_user(request, graphql_organization):
    """Configure a fake user to be used in graphql calls"""
    functional_marker = request.node.get_closest_marker("functional")
    permissions = []
    if functional_marker:
        permissions = functional_marker.kwargs.get('permissions', [])

    user = create_user(organization=graphql_organization, permissions=permissions)
    configure_fake_login(user)
    return user


def get_context_meta() -> dict:
    return dict(
        HTTP_USER_AGENT='test agent',
        HTTP_ORIGIN='test_suite',
        REMOTE_HOST='0.0.0.0',
        REQUEST_METHOD='TEST',
        HTTP_AUTHORIZATION='fake_JWT',
    )


@pytest.fixture
def graphql_client(client, graphql_organization, graphql_user):
    """Configure a graphql client with the a context to make calls in behalf
    of an user matching metadata provided from @pytest.mark.functional()"""
    runner = client.execute

    def execute_with_context(*args, **kwargs):
        context = _context(graphql_organization)
        return runner(*args, context=context, **kwargs)

    client.execute = execute_with_context
    client.context = dict(organization=graphql_organization, user=graphql_user)
    return client


@pytest.fixture
def create_permission_groups():
    groups = [
        'premium_super',
        'premium_admin',
        'premium_member',
        'premium_viewer',
        'premium_sales',
    ]

    for group_name in groups:
        Group.objects.create(name=group_name)


@pytest.fixture
def graphql_audit_user(request, graphql_audit_firm):
    """Configure a fake user to be used in graphql calls"""
    functional_marker = request.node.get_closest_marker("functional")
    permissions = []
    if functional_marker:
        permissions = functional_marker.kwargs.get('permissions', [])

    user = create_user_auditor(
        permissions=permissions,
        with_audit_firm=True,
        audit_firm=graphql_audit_firm.name,
        role=AUDITOR_ADMIN,
    ).user
    configure_fake_login(user)
    return user


@pytest.fixture
def graphql_audit_client(client, graphql_audit_firm, graphql_audit_user):
    """Configure a graphql client with the a context to make calls in behalf
    of an user matching metadata provided from @pytest.mark.functional()"""
    runner = client.execute

    def execute_with_context(*args, **kwargs):
        context = _context(graphql_audit_firm)
        return runner(*args, context=context, **kwargs)

    client.execute = execute_with_context
    client.context = dict(user=graphql_audit_user)
    return client


@pytest.fixture(autouse=True, scope='session')
def configure_fake_pdf_from_string():
    def fake_from_string(
        input,
        output_path,
        options=None,
        toc=None,
        cover=None,
        css=None,
        configuration=None,
        cover_first=False,
    ):
        return "This is a Test PDF".encode()

    import pdfkit

    pdfkit.from_string = fake_from_string


@pytest.fixture(autouse=True, scope='session')
def configure_fake_pdf_from_file():
    def fake_from_file(
        input,
        output_path,
        options=None,
        toc=None,
        cover=None,
        css=None,
        configuration=None,
        cover_first=False,
    ):
        return "This is a Test PDF".encode()

    import pdfkit

    pdfkit.from_file = fake_from_file


@pytest.fixture(autouse=True, scope='session')
def configure_fake_pdf_merge():
    def fake_merge(*pdfs):
        return io.BytesIO(b'This is a test merge')

    from laika.utils import pdf

    pdf.merge = fake_merge


@pytest.fixture(autouse=True, scope='session')
def configure_fake_pdf_stamp():
    def fake_stamp(stamp_pdf_path, pdf_path):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temporary_file:
            temporary_file.write('This is a Test PDF stamped'.encode('utf-8'))
        return temporary_file.name

    import pypdftk

    pypdftk.stamp = fake_stamp


@pytest.fixture(autouse=True, scope='session')
def configure_fake_pdf_concat():
    def fake_concat(files):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temporary_file:
            temporary_file.write('This is a Test PDF stamped'.encode('utf-8'))
        return temporary_file.name

    import pypdftk

    pypdftk.concat = fake_concat


@pytest.fixture(autouse=True, scope='session')
def configure_fake_get_num_pages():
    def fake_get_num_pages(pdf_path):
        return 1

    import pypdftk

    pypdftk.get_num_pages = fake_get_num_pages


#
# Onboarding Fixtures
#
@pytest.fixture
def graphql_onboarding(graphql_organization):
    graphql_organization.state = ONBOARDING
    graphql_organization.save()
    return graphql_organization.onboarding.first()


def pytest_collection_modifyitems(items):
    # Test with functional mark will have django_db mark
    for item in items:
        functional_marker = item.get_closest_marker("functional")
        if functional_marker:
            item.add_marker(
                pytest.mark.django_db(databases=['default', 'query_monitor'])
            )


def _context(organization):
    encoded_jwt = jwt.encode(
        {'custom:organizationId': str(organization.id)}, 'secret', algorithm='HS256'
    )
    context = Context(
        headers={'Authorization': encoded_jwt},
        organization=organization,
        # TODO: Find an easy way to hydrate Context
        FILES={},
        META=get_context_meta(),
    )
    context.loaders = Loaders(context)
    return context


@pytest.fixture
def jwt_http_client(graphql_organization):
    encoded_jwt = jwt.encode(
        {'custom:organizationId': str(graphql_organization.id)},
        'secret',
        algorithm='HS256',
    )
    c = DjangoClient()
    post = c.post
    get = c.get

    def execute_post(path, data):
        return post(
            path, data=data, content_type=JSON_CONTENT_TYPE, authorization=encoded_jwt
        )

    def execute_get(path):
        return get(path, content_type=JSON_CONTENT_TYPE, authorization=encoded_jwt)

    c.post = execute_post
    c.get = execute_get
    return c


@pytest.fixture
def error_logs(capsys):
    from laika.utils.exceptions import logger

    logger.error = print
    return capsys


@pytest.fixture
def different_organization(request):
    """Configure a fake org to be used in graphql calls"""
    functional_marker = request.node.get_closest_marker("functional")
    flags = []
    if functional_marker:
        flags = functional_marker.kwargs.get('feature_flags', [])
    return create_organization(flags=flags)


# Comments
COMMENT_CONTENT = 'My comment'
REPLY_CONTENT = 'This is a reply'


@pytest.fixture
def comment(graphql_user):
    return Comment.objects.create(owner=graphql_user, content=COMMENT_CONTENT)


@pytest.fixture
def reply(graphql_user, comment):
    reply = Reply.objects.create(
        owner=graphql_user, content=REPLY_CONTENT, parent=comment
    )

    comment.replies.add(reply)
    return reply


@pytest.fixture
def resolved_comment(graphql_user):
    return Comment.objects.create(
        owner=graphql_user,
        content=COMMENT_CONTENT,
        resolved_by=graphql_user,
        resolved_at=datetime.now(),
        state=RESOLVED,
    )


@pytest.fixture
def payload_for_access_review_tests(graphql_organization):
    vendor = create_vendor(name='testing vendor')
    integration = create_integration(None, vendor=vendor)
    connection_account = create_connection_account(
        'testing connection account',
        integration=integration,
    )
    laika_object_type = create_object_type(
        graphql_organization,
        type_name=USER.type,
    )
    laika_object = create_laika_object(
        laika_object_type,
        connection_account,
        data=generate_testing_role('before update'),
    )
    access_review = AccessReview.objects.create(
        organization=graphql_organization,
        name='testing access review',
    )
    access_review_vendor = AccessReviewVendor.objects.create(
        access_review=access_review, vendor=vendor
    )
    organization_vendor = create_organization_vendor(
        access_review.organization, access_review_vendor.vendor
    )
    AccessReviewVendorPreference.objects.create(
        organization_vendor=organization_vendor,
        organization=organization_vendor.organization,
        vendor=organization_vendor.vendor,
    )
    access_review_object = AccessReviewObject.objects.create(
        access_review_vendor=access_review_vendor,
        laika_object=laika_object,
        original_access=json.dumps(laika_object.data['Roles']),
    )
    return laika_object, access_review_object, connection_account


@pytest.fixture
def action_item(graphql_organization):
    return ActionItem.objects.create(
        description='action item test',
        metadata={
            'organizationId': str(graphql_organization.id),
        },
    )


@pytest.fixture
def action_item_evidence(graphql_organization, action_item):
    file_name = 'test file 2'
    evidence = Evidence.objects.create(
        name=file_name,
        description='',
        organization=graphql_organization,
        type=FILE,
        file=File(file=tempfile.TemporaryFile(), name=file_name),
    )
    action_item.evidences.add(evidence)
    return evidence


@pytest.fixture
def http_client(graphql_organization, graphql_user):
    client = DjangoClient(
        HTTP_ORIGIN='http://localhost:3000', HTTP_AUTHORIZATION=OKTA_API_KEY
    )
    post = client.post
    put = client.put
    patch = client.patch

    def execute_post(path, data):
        return post(path, data=data, content_type=JSON_CONTENT_TYPE)

    def execute_put(path, data):
        return put(path, data=data, content_type=JSON_CONTENT_TYPE)

    def execute_patch(path, data):
        return patch(path, data=data, content_type=JSON_CONTENT_TYPE)

    client.post = execute_post
    client.put = execute_put
    client.patch = execute_patch
    return client
