comments_feature_flag = 'commentsFeatureFlag'
dashboard_feature_flag = 'dashboardFeatureFlag'
integrations_feature_flag = 'integrationsFeatureFlag'
objects_feature_flag = 'objectsFeatureFlag'
playbooks_feature_flag = 'playbooksFeatureFlag'
audits_feature_flag = 'auditsFeatureFlag'
mfa_feature_flag = 'mfaFeatureFlag'
new_controls_feature_flag = 'newControlsFeatureFlag'
okta_feature_flag = 'oktaFeatureFlag'
read_only_playbooks_feature_flag = 'readOnlyPlaybooksFeatureFlag'
background_check_feature_flag = 'backgroundCheckFeatureFlag'
sso_feature_flag = 'ssoFeatureFlag'
pentest_feature_flag = 'pentestFeatureFlag'
new_training_feature_flag = 'trainingFeatureFlag'
onboarding_v2_flag = 'onboardingV2FeatureFlag'

# auditor feature flags
fieldwork_feature_flag = 'fieldworkFeatureFlag'
evidence_feature_flag = 'evidenceFeatureFlag'


FEATURE_FLAGS = [
    (dashboard_feature_flag, 'Dashboard'),
    (comments_feature_flag, 'Comments'),
    (playbooks_feature_flag, 'Playbooks'),
    (objects_feature_flag, 'Objects'),
    (integrations_feature_flag, 'Integrations'),
    (audits_feature_flag, 'Audits'),
    (new_controls_feature_flag, 'My Compliance'),
]

DEFAULT_FIRM_FEATURE_FLAGS = {
    'FIELDWORK_FEATURE_FLAG': dict(name=fieldwork_feature_flag, is_enabled=True),
    'EVIDENCE_FEATURE_FLAG': dict(name=evidence_feature_flag, is_enabled=True),
}

DEFAULT_ORGANIZATION_FEATURE_FLAGS = {
    'DASHBOARD_FEATURE_FLAG': dict(
        name=dashboard_feature_flag, display_name='Dashboard', is_enabled=True
    ),
    'COMMENTS_FEATURE_FLAG': dict(
        name='commentsFeatureFlag', display_name='Comments', is_enabled=True
    ),
    'PLAYBOOKS_FEATURE_FLAG': dict(
        name=playbooks_feature_flag, display_name='Playbooks', is_enabled=False
    ),
    'OBJECTS_FEATURE_FLAG': dict(
        name=objects_feature_flag, display_name='Objects', is_enabled=True
    ),
    'INTEGRATIONS_FEATURE_FLAG': dict(
        name=integrations_feature_flag, display_name='Integrations', is_enabled=True
    ),
    'AUDITS_FEATURE_FLAG': dict(
        name=audits_feature_flag, display_name='Audits', is_enabled=False
    ),
    'MY_COMPLIANCE_FEATURE_FLAG': dict(
        name=new_controls_feature_flag, display_name='My Compliance', is_enabled=True
    ),
    'PENTEST_FEATURE_FLAG': dict(
        name=pentest_feature_flag, display_name='Pentest', is_enabled=True
    ),
    'ONBOARDING_V2_FEATURE_FLAG': dict(
        name=onboarding_v2_flag, display_name='OnboardingV2', is_enabled=True
    ),
}

(
    INTEGRATIONS_FEATURE_FLAG,
    OBJECTS_FEATURE_FLAG,
    PLAYBOOKS_FEATURE_FLAG,
    DASHBOARD_FEATURE_FLAG,
    COMMENTS_FEATURE_FLAG,
    AUDITS_FEATURE_FLAG,
    MY_COMPLIANCE_FEATURE_FLAG,
    PENTEST_FEATURE_FLAG,
    ONBOARDING_V2_FEATURE_FLAG,
) = DEFAULT_ORGANIZATION_FEATURE_FLAGS.values()
