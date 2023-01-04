import logging

import graphene
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from laika import types
from laika.auth import login_required, permission_required
from laika.types import UploadResultType
from laika.utils.exceptions import ServiceException
from laika.utils.history import create_revision
from laika.utils.spreadsheet import create_workbook, get_workbook_rows
from objects.tasks import find_match_for_lo_background_check
from seeder.seeders.commons import are_columns_empty, are_columns_required_empty
from user.constants import (
    ACTIVE_PEOPLE_SHEET_TITLE,
    ALL_HEADERS,
    HEADER_BULK_USERS,
    LAIKA_PERMISSION,
    REQUIRED_USER_HEADERS,
    USER_ROLES,
)
from user.models import User
from user.types import UserType
from user.utils.invite_user import invite_user
from user.utils.parse_user import (
    parse_user_fields,
    parse_user_from_excel,
    sanitize_dict,
)

HEADER_NAMES = [header['name'] for header in ALL_HEADERS]
HEADER_NAMES_BULK_USERS = [header['name'] for header in HEADER_BULK_USERS]
ICON_NAME = 'group'
ICON_COLOR = 'brandViolet'
MAX_ROWS = 500
HEADERS_INDEX_POSITION = 2

logger = logging.getLogger(__name__)


def map_user_to_dic(row, headers):
    headers_len = len(headers)
    return dict(zip(headers, [entry for entry in row[0:headers_len]]))


def calc_successful_rows(sheet_max_row, ignored_rows, failed_rows):
    return sheet_max_row - len(ignored_rows) - len(failed_rows) - 2


def get_laika_user(email):
    return (
        User.objects.filter(email=email, username__isnull=False)
        .exclude(username__exact='')
        .first()
    )


def update_user(user, user_dict):
    parsed_user = parse_user_fields(
        user.organization,
        {
            **user_dict,
            'username': user.username,
            'role': user_dict['role'] or user.role,
        },
    )
    User.objects.filter(pk=user.id).update(**parsed_user)
    return User.objects.get(pk=user.id)


def is_row_valid(is_from_invite_user, failed_rows, ignored_rows, row_num, user_dic):
    if are_columns_empty(user_dic, HEADER_NAMES):
        logger.warning(f'Row ignored because all the columns are empty: {row_num}')
        ignored_rows.append(row_num)
        return False

    if (
        is_from_invite_user
        and are_columns_required_empty(user_dic, HEADER_NAMES_BULK_USERS)
        or are_columns_required_empty(user_dic, REQUIRED_USER_HEADERS)
    ):
        logger.warning(f'Some columns are empty on row: {row_num}')
        failed_rows.append(row_num)
        return False

    try:
        validate_email(user_dic.get('Email', '').strip())
    except ValidationError as e:
        failed_rows.append(row_num)
        logger.exception(
            'Bulk invite user has failed. Email is wrong '
            f'{user_dic.get("Email")} - Error {e}'
        )
        return False

    return True


def get_laika_permission(laika_permission):
    if laika_permission:
        user_role = str(laika_permission).upper()
        return USER_ROLES.get(user_role, USER_ROLES['VIEWER']), user_role
    return laika_permission, ''


def bulk_invite_users(info, input):
    organization = info.context.user.organization
    failed_rows = []
    ignored_rows = []
    invited_users = []
    is_from_invite_user = input.get('is_from_invite_user')

    headers_to_use = HEADER_NAMES_BULK_USERS if is_from_invite_user else HEADER_NAMES

    workbook = create_workbook(
        input.invite_user_file,
        MAX_ROWS,
        ACTIVE_PEOPLE_SHEET_TITLE,
        headers_to_use,
        HEADERS_INDEX_POSITION,
    )
    sheet = workbook.active
    is_valid, rows, headers = get_workbook_rows(
        workbook, HEADERS_INDEX_POSITION, headers_to_use
    )

    if not rows:
        raise ServiceException('The document you are trying to add is empty')

    if not is_valid:
        upload_result = UploadResultType(
            title='Users',
            icon_name=ICON_NAME,
            icon_color=ICON_COLOR,
            message='Upload Failed: Incorrect headers',
        )

        return [upload_result, invited_users]

    for row_num, row_values in rows:
        user_dic = map_user_to_dic(row_values, headers)
        laika_permission = user_dic.get(LAIKA_PERMISSION)
        user_dic['Role'], user_role = get_laika_permission(laika_permission)
        if not is_row_valid(
            is_from_invite_user, failed_rows, ignored_rows, row_num, user_dic
        ):
            continue

        user_dict = sanitize_dict(user_dic)
        parsed_user = parse_user_from_excel(user_dict, organization)
        laika_user = get_laika_user(parsed_user.get('email'))
        if laika_user:
            updated_user = update_user(laika_user, parsed_user)
            invited_users.append(updated_user)
        else:
            is_partial = (
                input.get('partial')
                or laika_permission is None
                or user_role not in USER_ROLES
            )
            invited_user = invite_user(organization, parsed_user, is_partial)
            invited_users.append(invited_user)

    organization_id = invited_users[0].organization.id
    find_match_for_lo_background_check.delay(
        [
            {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
            }
            for user in invited_users
        ],
        organization_id,
    )

    upload_result = UploadResultType(
        title='Users',
        icon_name=ICON_NAME,
        icon_color=ICON_COLOR,
        successful_rows=calc_successful_rows(sheet.max_row, ignored_rows, failed_rows),
        failed_rows=failed_rows,
        ignored_rows=ignored_rows,
    )

    return [upload_result, invited_users]


class BulkInviteUserInput(graphene.InputObjectType):
    invite_user_file = graphene.Field(types.InputFileType, required=True)
    partial = graphene.Boolean()
    is_from_invite_user = graphene.Boolean()


class BulkInviteUser(graphene.Mutation):
    class Arguments:
        input = BulkInviteUserInput(required=True)

    upload_result = graphene.List(UploadResultType, default_value=[])
    invited_users = graphene.List(UserType, default_value=[])

    @login_required
    @permission_required('user.change_user')
    @create_revision('Invited user')
    def mutate(self, info, input=None):
        upload_result, invited_users = bulk_invite_users(info, input)
        return BulkInviteUser([upload_result], invited_users)
