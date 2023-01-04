from objects.models import Attribute, LaikaObjectType
from objects.types import Types
from organization.models import Organization

TEXT = Types.TEXT.name
BOOLEAN = Types.BOOLEAN.name
DATE = Types.DATE.name
JSON = Types.JSON.name
NUMBER = Types.NUMBER.name
CONNECTION_NAME = 'Connection Name'
SOURCE_SYSTEM = 'Source System'
SINGLE_SELECT = Types.SINGLE_SELECT.name
IS_ACTIVE = 'Is Active'
EMAIL = 'Email'
FIRST_NAME = 'First Name'
LAST_NAME = 'Last Name'
CREATED_ON = 'Created On'
CREATED_AT = 'Created At'


class ObjectTypeSpec(object):
    def __init__(self, display_name, type, attributes, icon, color):
        self.display_name = display_name
        self.type = type
        self.attributes = attributes
        self.icon = icon
        self.color = color


class LOAttribute:
    def __init__(
        self,
        display_name,
        attribute_type,
        min_width=None,
        is_manually_editable=None,
        is_required=False,
    ):
        self.display_name = display_name
        self.attribute_type = attribute_type
        self.is_required = is_required
        if min_width is not None:
            self.min_width = min_width
        if is_manually_editable is not None:
            self.is_manually_editable = is_manually_editable


class SystemType:
    def data(self):
        return {
            getattr(type(self), field).display_name: value
            for field, value in self.__dict__.items()
        }

    @classmethod
    def attributes(cls):
        def build_attribute(field, index):
            attribute = {
                'name': field.display_name,
                'attribute_type': field.attribute_type,
                '_metadata': {'is_protected': True},
                'sort_index': index,
                'is_required': field.is_required,
            }
            if hasattr(field, 'min_width'):
                attribute['min_width'] = field.min_width
            if hasattr(field, 'is_manually_editable'):
                attribute['is_manually_editable'] = field.is_manually_editable
            return attribute

        fields = [v for v in cls.__dict__.values() if isinstance(v, LOAttribute)]
        return [build_attribute(f, i) for i, f in enumerate(fields, 1)]


class User(SystemType):
    id = LOAttribute('Id', TEXT, is_required=True)
    first_name = LOAttribute(FIRST_NAME, TEXT, is_required=True)
    last_name = LOAttribute(LAST_NAME, TEXT, is_required=True)
    email = LOAttribute(EMAIL, TEXT, is_required=True)
    is_admin = LOAttribute('Is Admin', BOOLEAN)
    title = LOAttribute('Title', TEXT)
    organization_name = LOAttribute('Organization Name', TEXT)
    roles = LOAttribute('Roles', TEXT)
    groups = LOAttribute('Groups', TEXT)
    applications = LOAttribute('Applications', TEXT)
    mfa_enabled = LOAttribute('Mfa Enabled', BOOLEAN)
    mfa_enforced = LOAttribute('Mfa Enforced', BOOLEAN)
    source_system = LOAttribute(SOURCE_SYSTEM, TEXT)
    connection_name = LOAttribute(CONNECTION_NAME, TEXT)


class ChangeRequest(SystemType):
    key = LOAttribute('Key', TEXT)
    title = LOAttribute('Title', TEXT)
    description = LOAttribute('Description', TEXT)
    issue_type = LOAttribute('Issue Type', TEXT)
    epic = LOAttribute('Epic', TEXT)
    project = LOAttribute('Project', TEXT)
    assignee = LOAttribute('Assignee', TEXT)
    reporter = LOAttribute('Reporter', TEXT)
    status = LOAttribute('Status', TEXT, is_required=True)
    approver = LOAttribute('Approver', TEXT)
    started = LOAttribute('Started', DATE)
    transitions_history = LOAttribute(
        'Transitions History',
        JSON,
        is_manually_editable=False,
    )
    ended = LOAttribute('Ended', DATE)
    url = LOAttribute('Url', TEXT)
    source_system = LOAttribute(SOURCE_SYSTEM, TEXT)
    connection_name = LOAttribute(CONNECTION_NAME, TEXT)


class PullRequest(SystemType):
    key = LOAttribute('Key', TEXT, is_required=True)
    repository = LOAttribute('Repository', TEXT, is_required=True)
    repository_visibility = LOAttribute('Repository Visibility', TEXT, is_required=True)
    title = LOAttribute('Title', TEXT, min_width=450, is_required=True)
    source = LOAttribute('Source', TEXT, is_required=True)
    target = LOAttribute('Target', TEXT, is_required=True)
    state = LOAttribute('State', TEXT, is_required=True)
    is_verified = LOAttribute('Is Verified', BOOLEAN)
    is_approved = LOAttribute('Is Approved', BOOLEAN)
    url = LOAttribute('Url', TEXT, min_width=300)
    approvers = LOAttribute('Approvers', TEXT)
    reporter = LOAttribute('Reporter', TEXT)
    created_on = LOAttribute(CREATED_ON, DATE)
    updated_on = LOAttribute('Updated On', DATE)
    organization = LOAttribute('Organization', TEXT)
    source_system = LOAttribute(SOURCE_SYSTEM, TEXT)
    connection_name = LOAttribute(CONNECTION_NAME, TEXT)


class Monitor(SystemType):
    id = LOAttribute('Id', TEXT)
    name = LOAttribute('Name', TEXT, is_required=True)
    type = LOAttribute('Type', TEXT, is_required=True)
    query = LOAttribute('Query', TEXT)
    tags = LOAttribute('Tags', TEXT)
    message = LOAttribute('Message', TEXT)
    overall_state = LOAttribute('Overall State', TEXT, is_required=True)
    created_at = LOAttribute(CREATED_AT, DATE, is_required=True)
    created_by_name = LOAttribute('Created By (Name)', TEXT)
    created_by_email = LOAttribute('Created By (Email)', TEXT)
    notification_type = LOAttribute('Notification Type', TEXT)
    destination = LOAttribute('Destination', TEXT)
    source_system = LOAttribute(SOURCE_SYSTEM, TEXT)
    connection_name = LOAttribute(CONNECTION_NAME, TEXT)


class Event(SystemType):
    id = LOAttribute('Id', TEXT, is_required=True)
    title = LOAttribute('Title', TEXT, is_required=True)
    text = LOAttribute('Text', TEXT)
    type = LOAttribute('Type', TEXT, is_required=True)
    priority = LOAttribute('Priority', TEXT, is_required=True)
    host = LOAttribute('Host', TEXT)
    device = LOAttribute('Device', TEXT)
    source = LOAttribute('Source', TEXT, is_required=True)
    event_date = LOAttribute('Event date', DATE, is_required=True)
    tags = LOAttribute('Tags', TEXT)
    source_system = LOAttribute(SOURCE_SYSTEM, TEXT)
    connection_name = LOAttribute(CONNECTION_NAME, TEXT)


class Account(SystemType):
    source_system = LOAttribute(SOURCE_SYSTEM, TEXT, is_required=True)
    connection_name = LOAttribute(CONNECTION_NAME, TEXT)
    is_active = LOAttribute(IS_ACTIVE, BOOLEAN)
    created_on = LOAttribute(CREATED_ON, DATE)
    updated_on = LOAttribute('Updated On', DATE)
    owner = LOAttribute('Owner', Types.USER.name)
    configurations = LOAttribute('Configurations', TEXT, is_required=True)
    number_of_records = LOAttribute('Number of Records', TEXT, min_width=400)


class Repository(SystemType):
    name = LOAttribute('Name', TEXT, is_required=True)
    organization = LOAttribute('Organization', TEXT)
    public_url = LOAttribute('Public URL', TEXT)
    is_active = LOAttribute(IS_ACTIVE, BOOLEAN, is_required=True)
    is_public = LOAttribute('Is Public', BOOLEAN, is_required=True)
    updated_at = LOAttribute('Updated At', DATE)
    created_at = LOAttribute(CREATED_AT, DATE, is_required=True)
    source_system = LOAttribute(SOURCE_SYSTEM, TEXT, is_required=True)
    connection_name = LOAttribute(CONNECTION_NAME, TEXT)


class Device(SystemType):
    id = LOAttribute('Id', TEXT, is_required=True)
    name = LOAttribute('Name', TEXT, is_required=True)
    device_type = LOAttribute('Device Type', SINGLE_SELECT, is_required=True)
    company_issued = LOAttribute('Company Issued', BOOLEAN)
    serial_number = LOAttribute('Serial Number', TEXT)
    model = LOAttribute('Model', TEXT)
    brand = LOAttribute('Brand', TEXT)
    operating_system = LOAttribute('Operating System', TEXT)
    os_version = LOAttribute('OS Version', TEXT)
    location = LOAttribute('Location', TEXT)
    owner = LOAttribute('Owner', TEXT, is_required=True)
    issuance_status = LOAttribute('Issuance Status', SINGLE_SELECT)
    anti_virus_status = LOAttribute('Anti Virus Status', SINGLE_SELECT)
    encryption_status = LOAttribute('Encryption Status', SINGLE_SELECT)
    purchased_on = LOAttribute('Purchased On', DATE)
    cost = LOAttribute('Cost', NUMBER)
    note = LOAttribute('Note', TEXT)
    source_system = LOAttribute(SOURCE_SYSTEM, TEXT)
    connection_name = LOAttribute(CONNECTION_NAME, TEXT)


class ServiceAccount(SystemType):
    id = LOAttribute('Id', TEXT, is_required=True)
    display_name = LOAttribute('Display Name', TEXT, is_required=True)
    description = LOAttribute('Description', TEXT)
    owner_id = LOAttribute('Owner Id', TEXT, is_required=True)
    is_active = LOAttribute(IS_ACTIVE, BOOLEAN, is_required=True)
    created_date = LOAttribute('Created Date', DATE, is_required=True)
    email = LOAttribute(EMAIL, TEXT)
    roles = LOAttribute('Roles', TEXT)
    source_system = LOAttribute(SOURCE_SYSTEM, TEXT)
    connection_name = LOAttribute(CONNECTION_NAME, TEXT)


class BackgroundCheck(SystemType):
    id = LOAttribute('Id', TEXT)
    first_name = LOAttribute(FIRST_NAME, TEXT)
    last_name = LOAttribute(LAST_NAME, TEXT)
    email = LOAttribute(EMAIL, TEXT)
    check_name = LOAttribute('Check Name', TEXT)
    status = LOAttribute('Status', TEXT)
    estimated_completion_date = LOAttribute('Estimated Completion Date', DATE)
    initiation_date = LOAttribute('Initiation Date', DATE)
    package = LOAttribute('Package', TEXT)
    link_people_table = LOAttribute('Link to People Table', TEXT, min_width=300)
    source_system = LOAttribute(SOURCE_SYSTEM, TEXT)
    connection_name = LOAttribute(CONNECTION_NAME, TEXT)
    people_status = LOAttribute('People Status', TEXT)


USER = ObjectTypeSpec(
    display_name='Integration User',
    type='user',
    icon='supervisor_account',
    color='accentOrange',
    attributes=User.attributes(),
)

CHANGE_REQUEST = ObjectTypeSpec(
    display_name='Change Request',
    type='change_request',
    icon='change_history',
    color='menuTier02',
    attributes=ChangeRequest.attributes(),
)

PULL_REQUEST = ObjectTypeSpec(
    display_name='Pull Request',
    type='pull_request',
    icon='code',
    color='accentGreen01',
    attributes=PullRequest.attributes(),
)

MONITOR = ObjectTypeSpec(
    display_name='Monitor',
    type='monitor',
    icon='warning',
    color='accentRed',
    attributes=Monitor.attributes(),
)

EVENT = ObjectTypeSpec(
    display_name='Event',
    type='event',
    icon='alarm',
    color='aquaTint80',
    attributes=Event.attributes(),
)

ACCOUNT = ObjectTypeSpec(
    display_name='Account',
    type='account',
    icon='business',
    color='purpleTint80',
    attributes=Account.attributes(),
)

REPOSITORY = ObjectTypeSpec(
    display_name='Repository',
    type='repository',
    icon='source',
    color='yellowTint50',
    attributes=Repository.attributes(),
)

DEVICE = ObjectTypeSpec(
    display_name='Device',
    type='device',
    icon='devices',
    color='aquaTint80',
    attributes=Device.attributes(),
)

SERVICE_ACCOUNT = ObjectTypeSpec(
    display_name='Service Account',
    type='service_account',
    icon='admin_panel_settings',
    color='brandColorB',
    attributes=ServiceAccount.attributes(),
)

BACKGROUND_CHECK = ObjectTypeSpec(
    display_name='Background Check',
    type='background_check',
    icon='verified',
    color='accentGreen03',
    attributes=BackgroundCheck.attributes(),
)


def resolve_laika_object_type(
    organization: Organization, spec: ObjectTypeSpec
) -> LaikaObjectType:
    display_index = LaikaObjectType.objects.count()
    laika_type, created = LaikaObjectType.objects.get_or_create(
        organization=organization,
        type_name=spec.type,
        is_system_type=True,
        defaults={
            'display_name': spec.display_name,
            'color': spec.color,
            'icon_name': spec.icon,
            'display_index': display_index + 1,
        },
    )
    if created:
        for attribute in spec.attributes:
            attribute.update(
                {'object_type': laika_type, '_metadata': {'is_protected': True}}
            )
            Attribute.objects.create(**attribute)

    return laika_type


LO_REQUIRED_FIELDS = {
    'event': ['Id', 'Title', 'Type', 'Priority', 'Source', 'Event Date'],
    'device': ['Id', 'Name', 'Device Type', 'Owner'],
    'incident': [
        'ID',
        'Name',
        'Date Opened',
        'Date Closed',
        'Details of Incident',
        'Criticality',
    ],
    'user': ['Id', FIRST_NAME, LAST_NAME, 'Email'],
    'monitor': ['Name', 'Type', 'Overall State', CREATED_AT, SOURCE_SYSTEM],
    'people': ['Name', 'Job title', 'Hire Date', 'Termination Date'],
    'pull_request': [
        'Key',
        'Repository',
        'Repository Visibility',
        'Title',
        'Source',
        'Target',
        'State',
    ],
    'repository': ['Name', IS_ACTIVE, 'Is Public', CREATED_AT, SOURCE_SYSTEM],
    'service_account': ['Id', 'Display Name', 'Owner id', IS_ACTIVE, 'Created Date'],
    'vendors': ['Name', 'Criticality'],
    'account': [SOURCE_SYSTEM, 'Connection Name', CREATED_ON, 'Owner'],
    'change_request': ['Status'],
}
