# Generated by Django 3.2.13 on 2022-06-27 18:14

from django.db import migrations

PERMISSIONS_DICT = {
    'Google Workspace': {
        "human-readable": [
            "Manage data access permissions for users on your domain",
            "See info about users on your domain",
            "View organization units on your domain",
            "View delegated admin roles for your domain",
        ],
        "granular-permissions": [
            "https://www.googleapis.com/auth/admin.directory.user.security",
            "https://www.googleapis.com/auth/admin.directory.user.readonly",
            "https://www.googleapis.com/auth/admin.directory.orgunit.readonly",
            "https://www.googleapis.com/auth/admin.directory.rolemanagement.readonly",
        ],
        "type": "Read/Write",
    },
    'Microsoft 365': {
        "human-readable": [
            "Read audit log data",
            "Read directory data",
            "Read group memberships",
            "Maintain access to data you have given it access to",
            "Read all users full profiles",
        ],
        "granular-permissions": [
            "AuditLog.Read.All",
            "Directory.Read.All",
            "GroupMember.Read.All",
            "offline_access",
            "User.Read.All",
        ],
        "type": "Read Only",
    },
    'Google Cloud Platform': {
        "human-readable": [
            "Read Cloudbuild builds",
            "Read Compute Engine Images & Instances",
            "Read IAM Roles & Service Accounts",
            "Read Cloud Logging buckets",
            "Read Cloud Monitoring alert policies",
            "Read Recommender instance recommendations",
            "Read Could Resource Manager projects",
            "Read ServiceUsage services",
        ],
        "granular-permissions": [
            "cloudbuild.builds.get",
            "cloudbuild.builds.list",
            "compute.images.list",
            "compute.instances.list",
            "iam.roles.get",
            "iam.roles.list",
            "iam.serviceAccounts.actAs",
            "iam.serviceAccounts.get",
            "iam.serviceAccounts.getIamPolicy",
            "iam.serviceAccounts.list",
            "logging.buckets.list",
            "monitoring.alertPolicies.list",
            "recommender.cloudsqlIdleInstanceRecommendations.get",
            "resourcemanager.projects.get",
            "resourcemanager.projects.getIamPolicy",
            "serviceusage.services.get",
            "serviceusage.services.list",
        ],
        "type": "Read Only",
    },
    'AWS': {
        "human-readable": [
            "Auto Scaling",
            "Cloudtrail",
            "Cloudwatch",
            "DynamoDB",
            "EC2",
            "Elastic Container Registry",
            "Elastic Kubernetes Service",
            "GuardDuty",
            "IAM",
            "Kinesis",
            "Key Management Service",
            "Describe logs",
            "S3",
            "Secrets Manager",
            "Redshift",
            "RDS",
            "Security Hub",
            "Serverless Application Repository",
            "SNS",
            "SQS",
            "Tag Editor",
        ],
        "granular-permissions": [
            "autoscaling:Describe*",
            "aws-portal:View*",
            "cloudtrail:DescribeTrails",
            "cloudtrail:GetEventSelectors",
            "cloudtrail:GetTrailStatus",
            "cloudwatch:Describe*",
            "config:Deliver*",
            "config:Describe*",
            "config:Get*",
            "config:List*",
            "config:Select*",
            "dynamodb:Describe*",
            "dynamodb:List*",
            "ec2:Describe*",
            "ecr-public:DescribeRepositories",
            "ecr:DescribeImagesecr:DescribeRepositories",
            "eks:DescribeCluster",
            "eks:ListClusters",
            "elasticache:Describe*",
            "guardduty:Describe*",
            "guardduty:Get*",
            "guardduty:List*",
            "iam:Get*",
            "iam:List*",
            "kinesis:Describe*",
            "kinesis:Get*",
            "kinesis:List*",
            "kms:Describe*",
            "kms:GetKeyRotationStatus",
            "kms:List*",
            "logs:Describe*",
            "organizations:Describe*",
            "organizations:List*",
            "rds:Describe*",
            "redshift:Describe*",
            "redshift:ViewQueriesInConsole",
            "s3:GetBucket*",
            "s3:GetEncryptionConfiguration",
            "s3:List*",
            "secretsmanager:Describe*",
            "secretsmanager:List*",
            "securityhub:Describe*",
            "securityhub:Get*",
            "securityhub:List*",
            "serverlessrepo:GetApplication",
            "sns:Get*",
            "sns:List*",
            "sqs:ListQueues",
            "tag:GetResources",
            "tag:GetTagKeys",
        ],
        "type": "Read Only",
    },
    'Microsoft Azure': {
        "human-readable": [
            "Read data in your organization's directory, such as users, groups and"
            " apps",
            "Read all your organization's policies",
            "Read all applications and service principals",
            "read your organization’s identity (authentication) providers’ properties",
        ],
        "granular-permissions": [
            "Directory.Read.All",
            "Policy.Read.All",
            "Application.Read.All",
            "IdentityProvider.Read.All",
        ],
        "type": "Read Only",
    },
    'Heroku': {
        "human-readable": ["Read teams", "Read team members"],
        "granular-permissions": ["api-key"],
        "type": "Read Only",
    },
    'GitLab': {
        "human-readable": [
            "Read Groups",
            "Read Group members",
            "Read Projects",
            "Read Merge Requests",
        ],
        "granular-permissions": ["read-api"],
        "type": "Read Only",
    },
    'Bitbucket': {
        "human-readable": [
            "Read Account",
            "Read Workspace membership",
            "Read Projects",
            "Read Repositories",
            "Read Repositories",
            "Read Issues",
            "Read Snippets",
            "Read Pipelines",
        ],
        "granular-permissions": [
            "Read Account",
            "Read Workspace membership",
            "Read Projects",
            "Read Repositories",
            "Read Repositories",
            "Read Issues",
            "Read Snippets",
            "Read Pipelines",
        ],
        "type": "Read Only",
    },
    'Github Apps': {
        "human-readable": ["Actions", "Metadata", "Pull Requests", "Members"],
        "granular-permissions": ["Actions", "Metadata", "Pull Requests", "Members"],
        "type": "Read Only",
    },
    'Sentry': {
        "human-readable": [
            "Projects",
            "Teams",
            "Alerts",
            "Members",
            "Organizations",
            "Events",
        ],
        "granular-permissions": [
            "project:read",
            "team:read",
            "alerts:read",
            "org:read",
            "member:read",
            "event:read",
        ],
        "type": "Read Only",
    },
    'Datadog': {
        "human-readable": [
            "Monitors",
            "Events",
            "Users",
        ],
        "granular-permissions": ["API Key", "Application Key"],
        "type": "Read Only",
    },
    'Jira': {
        "human-readable": [
            "View user profiles",
            "View Jira issue data",
            "Manage project settings",
        ],
        "granular-permissions": [
            "read:jira-work",
            "read:jira-user",
            "offline_access",
            "manage:jira-configuration",
        ],
        "type": "Read Only",
    },
    'Linear': {
        "human-readable": [
            "Users",
            "Projects",
            "Project Issues",
        ],
        "granular-permissions": ["read-only scope (Default)"],
        "type": "Read Only",
    },
    'Asana': {
        "human-readable": ["Projects", "Workspaces", "Users", "Tasks"],
        "granular-permissions": ["read-only scope (Default)"],
        "type": "Read Only",
    },
    'Shortcut': {
        "human-readable": ["Projects", "Epics", "Members", "Workflows"],
        "granular-permissions": ["API key access"],
        "type": "Read Only",
    },
    'Rippling': {
        "human-readable": [
            "Admin Department",
            "Admin Personal Email",
            "Company Activity Log",
            "Generate SAML assertions for employees",
            "Company Address",
            "Company Employment Types",
            "Read Employee Custom Fields",
            "Employee Level",
            "Employee Preferred First Name",
            "Employee Termination Date",
            "Company Custom Fields",
            "Employee Preferred Last Name",
            "Employee Department",
            "Company Titles",
            "Employee Number",
            "Employee Work email",
            "Company Phone Number",
            "Admin Phone Number",
            "Write SOC2 Report",
            "User ID",
            "Read Employee Work Location Id",
            "Company Teams",
            "Employee First name, last name",
            "Employee Employment type",
            "Admin Status",
            "Employee Phone Number",
            "Company Work Locations",
            "Employee Status",
            "Admin Work email",
            "Employee Manager",
            "Company Levels",
            "Admin First name, last name",
            "Admin Work location",
            "Write Hardware Report",
            "Employee Teams",
            "Company Legal Name",
            "Read Hardware Report",
            "Write group members",
            "Read SOC2 Report",
            "Employee Job Title",
            "Read groups",
            "Company Departments",
            "Read group members",
            "Employee Work location",
        ],
        "granular-permissions": [
            "Admin Department",
            "Admin Personal Email",
            "Company Activity Log",
            "Generate SAML assertions for employees",
            "Company Address",
            "Company Employment Types",
            "Read Employee Custom Fields",
            "Employee Level",
            "Employee Preferred First Name",
            "Employee Termination Date",
            "Company Custom Fields",
            "Employee Preferred Last Name",
            "Employee Department",
            "Company Titles",
            "Employee Number",
            "Employee Work email",
            "Company Phone Number",
            "Admin Phone Number",
            "Write SOC2 Report",
            "User ID",
            "Read Employee Work Location Id",
            "Company Teams",
            "Employee First name, last name",
            "Employee Employment type",
            "Admin Status",
            "Employee Phone Number",
            "Company Work Locations",
            "Employee Status",
            "Admin Work email",
            "Employee Manager",
            "Company Levels",
            "Admin First name, last name",
            "Admin Work location",
            "Employee Teams",
            "Company Legal Name",
            "Read Hardware Report",
            "Read SOC2 Report",
            "Employee Job Title",
            "Read groups",
            "Company Departments",
            "Read group members",
            "Employee Work location",
        ],
        "type": "Read/Write",
    },
    'Jamf': {
        "human-readable": [
            "Buildings",
            "Departments",
            "Computers Inventory",
            "Mobile Devices",
        ],
        "granular-permissions": ["Admin user"],
        "type": "Read Only",
    },
    'Slack': {
        "human-readable": [
            "View basic information about public channels in your workspace",
            "View messages and other content in public channels that Laika has been"
            " added to",
            "View basic information about private channels that Laika has been"
            " added to",
            "View people in your workspace",
            "View email addresses of people in your workspace",
            "Send messages as @heylaika",
            "Send messages to channels @heylaika isn't a member of",
            "Add shortcuts and/or slash commands that people can use",
        ],
        "granular-permissions": [
            "channels:history",
            "channels:read",
            "chat:write",
            "chat:write.public",
            "commands",
            "groups:read",
            "users:read",
            "users:read.email",
        ],
        "type": "Read Only",
    },
    'Vetty': {
        "human-readable": ["Get Applicants", "Get Screenings", "Get Packages"],
        "granular-permissions": ["Api Key"],
        "type": "Read Only",
    },
    'Okta': {
        "human-readable": [
            "Get Users",
            "Get Groups",
        ],
        "granular-permissions": ["Api Key"],
        "type": "Read Only",
    },
}


def add_permissions_to_version(apps, _):
    integration_version_model = apps.get_model('integration', 'IntegrationVersion')
    for vendor in PERMISSIONS_DICT:
        integration_version = integration_version_model.objects.filter(
            version_number='1.0.0', integration__vendor__name__iexact=vendor
        )
        if integration_version.exists():
            version = integration_version.first()
            version.metadata['permissions'] = PERMISSIONS_DICT.get(vendor, {})
            version.save()


class Migration(migrations.Migration):
    dependencies = [
        ('integration', '0054_add_integration_version'),
    ]

    operations = [migrations.RunPython(add_permissions_to_version)]
