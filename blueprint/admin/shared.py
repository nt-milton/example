from blueprint.choices import BlueprintPage
from blueprint.commons import AirtableSync
from blueprint.constants import FRAMEWORK_TAG, NAME, ROLES


def get_framework_tag_records(request) -> dict:
    framework_tag_airtable = AirtableSync(
        table_name=FRAMEWORK_TAG,
        blueprint_name=str(BlueprintPage.CERTIFICATION),
        required_fields=[NAME],
        request_user=request.user,
    )

    tags = {}
    for record in framework_tag_airtable.get_airtable_records():
        fields = framework_tag_airtable.get_record_fields(record)
        if not fields:
            continue
        tags[record.get('id')] = fields
    return tags


def get_roles_records(request) -> dict:
    roles_airtable = AirtableSync(
        table_name=ROLES,
        blueprint_name=str(BlueprintPage.CONTROLS),
        required_fields=[NAME],
        request_user=request.user,
    )

    roles = {}
    for record in roles_airtable.get_airtable_records():
        fields = roles_airtable.get_record_fields(record)
        if not fields:
            continue
        roles[record.get('id')] = fields
    return roles
