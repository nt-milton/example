import jwt
import pytest
from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_save

from laika.settings import OPEN_API_SECRET
from organization.models import ApiTokenHistory, Onboarding, OrganizationChecklistRun
from organization.signals import (
    execute_post_onboarding_actions,
    execute_pre_offboarding_actions,
)
from organization.utils.api_token_generator import generate_api_token
from organization.utils.email_domain import get_email_domain_from_users


@pytest.mark.functional()
def test_create_api_token(graphql_user, graphql_organization):
    create_test_group()
    token, record = generate_api_token(graphql_user, 'test token')
    token_record = ApiTokenHistory.objects.get(
        created_by=graphql_user, organization=graphql_organization, api_key=token
    )
    payload = jwt.decode(token, OPEN_API_SECRET)
    assert 'email' in payload
    assert record == token_record
    assert token_record.api_key == token


def create_test_group():
    group = Group.objects.create(name='open_api_admin')
    permissions = Permission.objects.filter(
        codename__in=[
            'view_laikaobjecttype',
            'add_laikaobject',
            'change_laikaobject',
            'delete_laikaobject',
            'view_laikaobject',
            'bulk_upload_object',
        ]
    )
    group.permissions.add(*permissions)


def disconnect_org_and_seeder_post_savings():
    post_save.disconnect(
        execute_post_onboarding_actions,
        sender=Onboarding,
        dispatch_uid="post_save_onboarding",
    )

    post_save.disconnect(
        execute_pre_offboarding_actions,
        sender=OrganizationChecklistRun,
        dispatch_uid="create_offboarding_run_document",
    )


@pytest.mark.functional()
def test_get_email_domain_from_users(graphql_user, graphql_organization):
    assert get_email_domain_from_users(graphql_organization.id) == '@heylaika.com'
