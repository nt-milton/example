import pytest
from django.test import Client

from audit.models import Audit, AuditAuditor, AuditFirm
from auditee.tests.queries import (
    GET_AUDITEE_POPULATION_COMMENT_USERS,
    GET_AUDITEE_POPULATION_COMMENTS_BY_POOL,
)
from fieldwork.types import PopulationCommentPoolsEnum
from organization.models import Organization
from population.models import PopulationComment
from user.constants import AUDITOR, ROLE_ADMIN, ROLE_SUPER_ADMIN
from user.models import Auditor, User
from user.tests.factory import create_user_auditor


@pytest.fixture
def auditor_user_in_audit_team(
    graphql_organization: Organization, graphql_audit_firm: AuditFirm, audit: Audit
) -> Auditor:
    auditor = create_user_auditor(
        email='auditor_user_in_team@heylaika.com',
        role=AUDITOR,
        with_audit_firm=True,
        audit_firm=graphql_audit_firm.name,
    )
    AuditAuditor.objects.create(auditor=auditor, audit=audit)
    return auditor


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_laika_pool_population_comment_users_by_super_admin(
    graphql_client: Client,
    graphql_user: User,
    auditor_user: Auditor,
    auditor_admin_user: Auditor,
    laika_admin_user: User,
    auditor_user_in_audit_team: Auditor,
    audit: Audit,
):
    graphql_user.role = ROLE_SUPER_ADMIN
    graphql_user.save()

    response_users_laika_pool = graphql_client.execute(
        GET_AUDITEE_POPULATION_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': PopulationCommentPoolsEnum.Laika.name},
    )

    users = response_users_laika_pool['data']['auditeePopulationCommentUsers']
    assert len(users) == 2


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_all_pool_population_comment_users_by_super_admin(
    graphql_client: Client,
    graphql_user: User,
    auditor_user: Auditor,
    auditor_admin_user: Auditor,
    laika_admin_user: User,
    auditor_user_in_audit_team: Auditor,
    audit: Audit,
):
    graphql_user.role = ROLE_SUPER_ADMIN
    graphql_user.save()

    response_users_all_pool = graphql_client.execute(
        GET_AUDITEE_POPULATION_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': PopulationCommentPoolsEnum.All.name},
    )

    users = response_users_all_pool['data']['auditeePopulationCommentUsers']
    assert len(users) == 4


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_lcl_cx_pool_population_comment_users_by_super_admin(
    graphql_client: Client,
    graphql_user: User,
    auditor_user: Auditor,
    auditor_admin_user: Auditor,
    laika_admin_user: User,
    auditor_user_in_audit_team: Auditor,
    audit: Audit,
):
    graphql_user.role = ROLE_SUPER_ADMIN
    graphql_user.save()

    response_users_lcl_cx_pool = graphql_client.execute(
        GET_AUDITEE_POPULATION_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': PopulationCommentPoolsEnum.LCL_CX.name},
    )

    users = response_users_lcl_cx_pool['data']['auditeePopulationCommentUsers']
    assert len(users) == 3


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_lcl_pool_population_comment_users_by_super_admin(
    graphql_client: Client,
    graphql_user: User,
    auditor_user: Auditor,
    auditor_admin_user: Auditor,
    laika_admin_user: User,
    auditor_user_in_audit_team: Auditor,
    audit: Audit,
):
    graphql_user.role = ROLE_SUPER_ADMIN
    graphql_user.save()

    response_users_lcl_pool = graphql_client.execute(
        GET_AUDITEE_POPULATION_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': PopulationCommentPoolsEnum.LCL.name},
    )

    users = response_users_lcl_pool['data']['auditeePopulationCommentUsers']
    assert users is None


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_laika_pool_population_comment_users_by_organization_admin(
    graphql_client: Client,
    graphql_user: User,
    auditor_user: Auditor,
    auditor_admin_user: Auditor,
    laika_admin_user: User,
    auditor_user_in_audit_team: Auditor,
    audit: Audit,
):
    graphql_user.role = ROLE_ADMIN
    graphql_user.save()

    laika_admin_user.role = ROLE_SUPER_ADMIN
    laika_admin_user.save()

    response_users_laika_pool = graphql_client.execute(
        GET_AUDITEE_POPULATION_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': PopulationCommentPoolsEnum.Laika.name},
    )

    users = response_users_laika_pool['data']['auditeePopulationCommentUsers']
    assert len(users) == 2


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_all_pool_population_comment_users_by_organization_admin(
    graphql_client: Client,
    graphql_user: User,
    auditor_user: Auditor,
    auditor_admin_user: Auditor,
    laika_admin_user: User,
    auditor_user_in_audit_team: Auditor,
    audit: Audit,
):
    graphql_user.role = ROLE_ADMIN
    graphql_user.save()

    laika_admin_user.role = ROLE_SUPER_ADMIN
    laika_admin_user.save()

    response_users_all_pool = graphql_client.execute(
        GET_AUDITEE_POPULATION_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': PopulationCommentPoolsEnum.All.name},
    )

    users = response_users_all_pool['data']['auditeePopulationCommentUsers']
    assert len(users) == 4


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_lcl_cx_pool_population_comment_users_by_organization_admin(
    graphql_client: Client,
    graphql_user: User,
    auditor_user: Auditor,
    auditor_admin_user: Auditor,
    laika_admin_user: User,
    auditor_user_in_audit_team: Auditor,
    audit: Audit,
):
    graphql_user.role = ROLE_ADMIN
    graphql_user.save()

    laika_admin_user.role = ROLE_SUPER_ADMIN
    laika_admin_user.save()

    response_users_lcl_cx_pool = graphql_client.execute(
        GET_AUDITEE_POPULATION_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': PopulationCommentPoolsEnum.LCL_CX.name},
    )

    users = response_users_lcl_cx_pool['data']['auditeePopulationCommentUsers']
    assert users is None


@pytest.mark.functional(permissions=['population.view_auditpopulation'])
def test_get_lcl_pool_population_comment_users_by_organization_admin(
    graphql_client: Client,
    graphql_user: User,
    auditor_user: Auditor,
    auditor_admin_user: Auditor,
    laika_admin_user: User,
    auditor_user_in_audit_team: Auditor,
    audit: Audit,
):
    graphql_user.role = ROLE_ADMIN
    graphql_user.save()

    laika_admin_user.role = ROLE_SUPER_ADMIN
    laika_admin_user.save()

    response_users_lcl_pool = graphql_client.execute(
        GET_AUDITEE_POPULATION_COMMENT_USERS,
        variables={'auditId': audit.id, 'pool': PopulationCommentPoolsEnum.LCL.name},
    )

    users = response_users_lcl_pool['data']['auditeePopulationCommentUsers']
    assert users is None


COMMENT_CONTENT = 'My comment'


@pytest.mark.functional(permissions=['comment.view_comment'])
def test_get_auditee_evidence_comments_by_pool(
    graphql_client, laika_admin_user, audit_population
):
    PopulationComment.objects.custom_create(
        owner=laika_admin_user,
        population_id=audit_population.id,
        tagged_users=[],
        content=COMMENT_CONTENT,
        pool=PopulationCommentPoolsEnum.Laika.value,
    )
    response = graphql_client.execute(
        GET_AUDITEE_POPULATION_COMMENTS_BY_POOL,
        variables={
            'auditId': audit_population.audit.id,
            'populationId': audit_population.id,
            'pool': PopulationCommentPoolsEnum.Laika.name,
        },
    )
    assert len(response['data']['auditeePopulationComments']) == 1
