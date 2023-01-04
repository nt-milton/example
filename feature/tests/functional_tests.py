import pytest

from audit.models import AuditorAuditFirm
from feature.constants import (
    DEFAULT_FIRM_FEATURE_FLAGS,
    audits_feature_flag,
    comments_feature_flag,
    fieldwork_feature_flag,
    onboarding_v2_flag,
    playbooks_feature_flag,
)
from feature.models import AuditorFlag, Flag
from feature.tests.mutations import UPDATE_FEATURE_FLAG
from organization.tasks import set_default_flags

from .queries import (
    GET_ALL_AUDITOR_FEATURE_FLAGS,
    GET_ALL_FEATURE_FLAGS,
    GET_AUDITOR_FEATURE_FLAG,
    GET_FEATURE_FLAGS,
)

default_feature_flags_len = 9


def set_default_auditor_flags(audit_firm):
    for flag in DEFAULT_FIRM_FEATURE_FLAGS.values():
        name, is_enabled = flag.values()
        AuditorFlag.objects.update_or_create(
            name=name, audit_firm_id=audit_firm.id, is_enabled=is_enabled
        )


@pytest.mark.functional()
def test_resolve_feature_flags(graphql_client, graphql_organization):
    set_default_flags(graphql_organization)

    executed = graphql_client.execute(
        GET_FEATURE_FLAGS,
        variables={'input': dict(organizationId=graphql_organization.id)},
    )

    data = executed['data']['flags']
    assert len(data) == default_feature_flags_len


@pytest.mark.functional(permissions=['user.change_concierge'])
def test_update_feature_flag(graphql_client, graphql_organization):
    flag, _ = Flag.objects.get_or_create(
        name=fieldwork_feature_flag,
        organization=graphql_organization,
        defaults={'is_enabled': False},
    )
    executed = graphql_client.execute(
        UPDATE_FEATURE_FLAG,
        variables={
            'input': dict(
                organizationId=str(graphql_organization.id),
                flags=[
                    {
                        'id': flag.id,
                        'name': flag.name,
                        'isEnabled': True,
                        'displayName': '',
                    }
                ],
            )
        },
    )

    assert executed['data']['updateFeature']
    flags = executed['data']['updateFeature']
    assert len(flags) == 1

    created_flag = Flag.objects.get(name=flag.name, organization=graphql_organization)

    assert created_flag.is_enabled is True


@pytest.mark.functional(permissions=['user.view_concierge'])
def test_get_all_feature_flag(graphql_client, graphql_organization):
    executed = graphql_client.execute(
        GET_ALL_FEATURE_FLAGS,
    )

    assert executed['data']['allFeatureFlags']
    feature_flags = executed['data']['allFeatureFlags']
    assert len(feature_flags) == default_feature_flags_len

    for ff in feature_flags:
        name, display_name, is_enabled = ff.values()
        if name == audits_feature_flag:
            assert is_enabled is False
        elif name == fieldwork_feature_flag:
            assert is_enabled is False
        elif name == playbooks_feature_flag:
            assert is_enabled is False
        elif name == onboarding_v2_flag:
            assert is_enabled is True
        else:
            assert is_enabled


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_auditor_flags(graphql_audit_client, graphql_audit_user):
    auditor_audit_firm = AuditorAuditFirm.objects.get(auditor__user=graphql_audit_user)
    set_default_auditor_flags(auditor_audit_firm.audit_firm)

    response = graphql_audit_client.execute(GET_ALL_AUDITOR_FEATURE_FLAGS)

    feature_flags = response['data']['auditorFlags']

    assert len(feature_flags) == 2


@pytest.mark.functional(permissions=['audit.view_audit'])
def test_get_auditor_flag(graphql_audit_client, graphql_audit_user):
    auditor_firm = AuditorAuditFirm.objects.get(auditor__user=graphql_audit_user)
    set_default_auditor_flags(auditor_firm.audit_firm)

    response = graphql_audit_client.execute(
        GET_AUDITOR_FEATURE_FLAG, variables={'name': fieldwork_feature_flag}
    )

    assert len(response['data']) == 1


@pytest.mark.functional()
def test_is_flag_enabled_for_organization(graphql_organization):
    set_default_flags(graphql_organization)
    assert (
        Flag.is_flag_enabled_for_organization(
            flag_name=comments_feature_flag, organization=graphql_organization
        )
        is True
    )
