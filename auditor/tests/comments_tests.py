import pytest
from django.test import Client

from audit.models import Audit
from auditor.tests.queries import GET_AUDITOR_COMMENT_MENTION_USERS_WITH_POOL
from fieldwork.types import PopulationCommentPoolsEnum
from user.models import Auditor, User


@pytest.mark.functional(permissions=['comment.view_comment'])
def test_get_lcl_pool_comment_mention_users(
    graphql_audit_client: Client,
    audit_auditor: Auditor,
    auditor_admin_user: Auditor,
    audit: Audit,
):
    response_users_lcl_pool = graphql_audit_client.execute(
        GET_AUDITOR_COMMENT_MENTION_USERS_WITH_POOL,
        variables={'auditId': audit.id, 'pool': PopulationCommentPoolsEnum.LCL.name},
    )

    users = response_users_lcl_pool['data']['auditorCommentMentionUsersWithPool']
    assert len(users) == 3


@pytest.mark.functional(permissions=['comment.view_comment'])
def test_get_all_pool_comment_mention_users(
    graphql_audit_client: Client,
    audit_auditor: Auditor,
    laika_admin_user: User,
    audit: Audit,
):
    response_users_all_pool = graphql_audit_client.execute(
        GET_AUDITOR_COMMENT_MENTION_USERS_WITH_POOL,
        variables={'auditId': audit.id, 'pool': PopulationCommentPoolsEnum.All.name},
    )

    users = response_users_all_pool['data']['auditorCommentMentionUsersWithPool']
    assert len(users) == 3


@pytest.mark.functional(permissions=['comment.view_comment'])
def test_get_lcl_cx_pool_comment_mention_users(
    graphql_audit_client: Client,
    audit_auditor: Auditor,
    laika_admin_user: User,
    laika_super_admin: User,
    audit: Audit,
):
    response_users_lcl_cx_pool = graphql_audit_client.execute(
        GET_AUDITOR_COMMENT_MENTION_USERS_WITH_POOL,
        variables={'auditId': audit.id, 'pool': PopulationCommentPoolsEnum.LCL_CX.name},
    )

    users = response_users_lcl_cx_pool['data']['auditorCommentMentionUsersWithPool']
    assert len(users) == 3
