import http
import json
import logging
import urllib.parse
from typing import List, Optional, Tuple

import django.utils.timezone as timezone
from django.contrib import admin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.validators import EmailValidator, ValidationError
from django.http.request import HttpRequest
from django.http.response import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseServerError,
    JsonResponse,
)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import FormView
from okta.models import User as OktaUser
from openpyxl import Workbook
from openpyxl.writer.excel import save_virtual_workbook

from action_item.constants import TYPE_POLICY
from action_item.models import ActionItem, ActionItemStatus
from laika.auth import api_key, login_required
from laika.aws import cognito
from laika.aws.ses import send_email
from laika.okta.api import OktaApi
from laika.settings import ENVIRONMENT, NO_REPLY_EMAIL, ORIGIN_LOCALHOST
from laika.utils.dates import now_date
from laika.utils.exceptions import ServiceException
from laika.utils.pdf import render_template_to_pdf
from laika.utils.spreadsheet import (
    CONTENT_TYPE,
    add_headers,
    add_list_validation,
    add_row_values,
    add_sheet_header,
)
from laika.utils.strings import get_random_otp
from sso.constants import DONE_ENABLED
from sso.models import IdentityProvider, IdentityProviderDomain
from user.constants import (
    A_UNICODE,
    ACTIVE_PEOPLE_SHEET_TITLE,
    DEACTIVATED_PEOPLE_SHEET_TITLE,
    DOMAIN_INDEX,
    EVIDENCE_HEADERS,
    INITIAL_USER_ROW,
    LOGIN_APP_URL,
    MAGIC_LINK_NOT_FOUND,
    MAGIC_LINK_TOKEN_EXPIRED,
    MAIN_HEADERS,
    OTP_DEFAULT_LENGTH,
    PASSWORD_TIMES,
    PEOPLE_HEADERS,
    PERMISSION_HEADERS,
    TIME_TO_CHANGE_PASS,
    USER_ROLES,
)
from user.forms import MigratePolarisUsersForm
from user.helpers import calculate_user_status
from user.models import (
    BACKGROUND_CHECK_STATUS,
    EMPLOYMENT_STATUS,
    EmploymentSubtype,
    EmploymentType,
    MagicLink,
    Team,
    User,
)
from user.utils.parse_user import map_choices_to_dic_inverted
from user.utils.role import get_label_role

OktaApi = OktaApi()

logger = logging.getLogger(__name__)


def get_full_name(u):
    return u.get_full_name().title() if u else 'Unnasigned'


def get_initials(u):
    if u:
        first_name = u.first_name.capitalize()
        last_name = u.last_name.capitalize()

        return f'{first_name[0]}{last_name[0]}'

    return '?'


def get_email(u):
    return u.email if u else '-'


def get_officers_pdf(officers, time_zone):
    return render_template_to_pdf(
        template='officer/export_officers.html',
        context={
            'officers': [
                {
                    'full_name': get_full_name(o.user),
                    'initials': get_initials(o.user),
                    'name': o.name,
                    'description': o.description,
                    'email': get_email(o.user),
                }
                for o in officers
            ],
        },
        time_zone=time_zone,
    )


@login_required
def export_officers(request):
    officers = request.user.organization.officers.all()
    time_zone = request.GET.get('timezone')
    pdf = get_officers_pdf(officers, time_zone)

    response = HttpResponse(pdf, content_type='application/pdf')
    date = now_date(time_zone, '%Y_%m_%d_%H_%M')
    file_name = f'Officers Details_{date}.pdf'
    response['Content-Disposition'] = f'attachment;filename="{file_name}"'
    return response


def get_formatted_members(team_members):
    return [
        {
            'full_name': get_full_name(m.user),
            'initials': get_initials(m.user),
            'role': m.role,
            'phone': m.phone,
            'email': get_email(m.user),
        }
        for m in team_members
    ]


def get_team_pdf(team, time_zone):
    team_members = team.members.all()
    team_name = team.name.title()
    return render_template_to_pdf(
        template='team/export_team.html',
        context={
            'team': {
                'name': team_name,
                'notes': team.notes,
                'charter': team.charter,
                'members': get_formatted_members(team_members),
            },
        },
        time_zone=time_zone,
    )


def get_key_from_choices(choices: List) -> List:
    return [item[0] for item in choices]


def map_user_row(headers, user):
    dict_user = vars(user)
    mapped_user = {
        header.get('key'): dict_user.get(header.get('key'), '') for header in headers
    }
    if 'manager_email' in mapped_user:
        manager = user.manager_user.first()
        mapped_user['manager_email'] = manager.email if manager else ''

    user_field_choices = [
        'role',
        'employment_type',
        'employment_subtype',
        'background_check_status',
        'employment_status',
    ]

    for field in user_field_choices:
        if field in mapped_user:
            if field == 'role':
                mapped_user['role'] = get_label_role(user.role)
            else:
                # Uses the build method for choices that are enums
                _method = f'get_{field}_display'
                mapped_user[field] = getattr(user, _method, lambda: None)()

    return mapped_user


@login_required
def export_team(request, team_id):
    time_zone = request.GET.get('timezone')

    team = Team.objects.get(id=team_id)
    team_name = team.name.title()
    pdf = get_team_pdf(team, time_zone)

    response = HttpResponse(pdf, content_type='application/pdf')
    date = now_date(time_zone, '%Y_%m_%d_%H_%M')
    file_name = f'{team_name}_{date}.pdf'
    response['Content-Disposition'] = f'attachment;filename="{file_name}"'
    return response


@csrf_exempt
@login_required
def export_template(request):
    model = request.GET.get('model')
    is_evidence = request.GET.get('is_evidence') == 'true'
    exclude_users = request.GET.get('exclude_users') == 'true'
    workbook = Workbook()
    sheet = workbook.active
    headers = []
    headers.extend(MAIN_HEADERS)
    title = ACTIVE_PEOPLE_SHEET_TITLE

    if model == 'user':
        headers.extend(PERMISSION_HEADERS)
        add_roles_validation(sheet)

    if model == 'people':
        headers.extend(PEOPLE_HEADERS)

    if model == 'full':
        headers.extend(PERMISSION_HEADERS)
        headers.extend(PEOPLE_HEADERS)
        is_evidence and headers.extend(EVIDENCE_HEADERS)

    validation_options = [
        {
            'key': 'role',
            'options': USER_ROLES,
            'filter_out': lambda role: role != 'SUPER_ADMIN',
        },
        {
            'key': 'employment_type',
            'options': map_choices_to_dic_inverted(EmploymentType.choices),
        },
        {
            'key': 'employment_subtype',
            'options': map_choices_to_dic_inverted(EmploymentSubtype.choices),
        },
        {
            'key': 'background_check_status',
            'options': map_choices_to_dic_inverted(BACKGROUND_CHECK_STATUS),
        },
        {
            'key': 'employment_status',
            'options': map_choices_to_dic_inverted(EMPLOYMENT_STATUS),
        },
    ]
    for validation in validation_options:
        add_validation(sheet, headers, validation)

    organization = request.user.organization
    sheet.title = title
    add_sheet_header(len(headers), title, sheet)
    add_headers(sheet, headers)
    users = User.objects.filter(organization=organization).exclude(
        role=USER_ROLES.get('SUPER_ADMIN')
    )
    users_policies = None
    if is_evidence:
        users_policies = get_policies_evidence(users)
        sheet_deactivated_people = workbook.create_sheet(DEACTIVATED_PEOPLE_SHEET_TITLE)
        add_headers(sheet_deactivated_people, headers)
        cleaned_users = clean_users_to_export(
            User.all_objects.only_deleted().filter(organization=organization)
        )
        add_row_values(
            sheet_deactivated_people,
            headers,
            map_user_row,
            cleaned_users,
            INITIAL_USER_ROW,
        )

    cleaned_users = clean_users_to_export(users, users_policies)
    if not exclude_users:
        add_row_values(sheet, headers, map_user_row, cleaned_users, INITIAL_USER_ROW)

    response = HttpResponse(
        content=save_virtual_workbook(workbook), content_type=CONTENT_TYPE
    )
    response['Content-Disposition'] = 'attachment; filename="User.xlsx"'

    return response


def get_policies_evidence(users):
    action_items = ActionItem.objects.filter(
        assignees__in=users, metadata__type=TYPE_POLICY
    ).values('name', 'assignees__id', 'status', 'completion_date')
    users_policies = {}
    for item in action_items:
        policies = users_policies.setdefault(item.get('assignees__id'), [[], []])
        status = item.get('status')
        # Unacknowledged Policies
        content_index = 1
        content = item.get('name', '')
        if status == ActionItemStatus.COMPLETED.value:
            # Acknowledgement Policies
            content_index = 0
            completion_date = item.get('completion_date')
            format_date = (
                completion_date.strftime('%Y-%m-%d') if completion_date else '-'
            )
            content += f"({format_date})"
        content += '\n'
        policies[content_index].append(content)

    return users_policies


def convert_user_date_fields_to_str(user):
    fields = [
        'last_login',
        'date_joined',
        'updated_at',
        'deleted_at',
        'background_check_passed_on',
        'start_date',
        'end_date',
        'invitation_sent',
    ]

    for field in fields:
        value = getattr(user, field)
        setattr(user, field, str(value) if value else '')
    return user


def clean_users_to_export(users, users_policies=None):
    result = []
    for user in users:
        if not user.is_active:
            user.role = ''
        user = convert_user_date_fields_to_str(user)
        if users_policies:
            policies = users_policies.get(user.id, [[], []])
            user.acknowledged_policies = ''.join(policies[0])
            user.unacknowledged_policies = ''.join(policies[1])
        result.append(user)
    return result


def add_roles_validation(sheet):
    roles = [key.title() for key in USER_ROLES.keys() if key != 'SUPER_ADMIN']
    add_list_validation(roles, sheet, 'D')


def add_validation(sheet, headers, validation_option):
    key = validation_option.get('key')
    options = validation_option.get('options')
    filter_out = validation_option.get('filter_out', lambda _: True)
    for idx, header in enumerate(headers):
        if header.get('key') == key:
            values = [
                key.title().replace('_', ' ')
                for key in options.keys()
                if filter_out(key)
            ]
            add_list_validation(values, sheet, chr(A_UNICODE + idx))
            break


def value_to_label(key, options, data):
    for option_key in options:
        if data[key] == options[option_key]:
            return option_key.title()


def invalid_request():
    return HttpResponseBadRequest('Invalid Request')


def email_validator(email: Optional[str]) -> Optional[str]:
    if not email:
        return None

    validator = EmailValidator()
    try:
        tokens = email.split('@')
        email = urllib.parse.quote_plus(tokens[0]) + '@' + tokens[1]
        logger.info(f'❗️ Validating SSO Login Username: {email}')
        validator(email)

        return email
    except ValidationError as e:
        logger.exception(f'Error validating the username for SSO: {e}')
        return None


def is_valid_to_change_okta_password(db_user: User) -> bool:
    if db_user.invitation_sent:
        try:
            time_changed = db_user.invitation_sent
            if get_seconds_until_today(time_changed) >= PASSWORD_TIMES['THREE_HOURS']:
                return True
        except Exception as e:
            logger.warning(f'Error validating okta data: {e}')
            raise e
    return False


# TODO: Extract some blocks of code into smaller methods
def validate_user_for_otp(
    email: Optional[str],
) -> Tuple[Optional[HttpResponse], Optional[OktaUser], Optional[str]]:
    email = email_validator(email)
    if not email:
        return invalid_request(), None, None

    try:
        okta_user = OktaApi.get_user_by_email(email)
        db_user = User.objects.filter(email__iexact=email).first()
        if not okta_user or not db_user:
            return HttpResponseNotFound(f'User {email} not found'), None, None

        if not is_valid_to_change_okta_password(db_user):
            msg = f'Not allow to change password before {TIME_TO_CHANGE_PASS}'
            logging.warning(msg)
            return (
                HttpResponse(content=msg, status=http.HTTPStatus.NOT_ACCEPTABLE),
                None,
                None,
            )

        return None, okta_user, email
    except Exception as e:
        logger.warning(f'Error when validating user for otp: {e}')
        return (
            HttpResponse(
                content='Fatal Error', status=http.HTTPStatus.INTERNAL_SERVER_ERROR
            ),
            None,
            None,
        )


def validate_otp_from_request(otp: Optional[str]) -> bool:
    if not otp:
        return False
    if not otp.isnumeric():
        return False
    if len(otp) != OTP_DEFAULT_LENGTH:
        return False
    return True


@api_key
@csrf_exempt
@require_POST
def get_okta_temporary_password(request):
    body_obj = json.loads(request.body.decode('utf-8'))
    email = body_obj.get('email')
    otp = body_obj.get('otp')

    if not email or not otp:
        return invalid_request()

    http_response, okta_user, email = validate_user_for_otp(email)
    if http_response or not okta_user or not email:
        return http_response

    if not validate_otp_from_request(otp):
        return invalid_request()

    try:
        db_user = User.objects.get(email__iexact=email)

        if not MagicLink.objects.get(user=db_user, temporary_code=otp).is_otp_valid:
            return HttpResponseForbidden('OTP is nor valid')

        db_user.password_expired = False
        db_user.invitation_sent = timezone.now()
        db_user.save()

        return HttpResponse(
            content=OktaApi.get_one_time_token(okta_user.id),
            status=http.HTTPStatus.ACCEPTED,
        )
    except User.DoesNotExist as e:
        logger.warning(f'Error: {e}')
        return HttpResponseNotFound(f'User: {email} not found')
    except MagicLink.DoesNotExist as e:
        logger.warning(f'Error: {e}')
        return HttpResponseNotFound(f'OTP: {otp} not found')
    except Exception as e:
        logger.warning(f'Error when getting one time token for {email}. Trace: {e}')
        return HttpResponseServerError('Service error')


@api_key
@csrf_exempt
@require_POST
def get_one_time_token(request: HttpRequest):
    body_obj = json.loads(request.body.decode('utf-8'))
    email = body_obj.get('email')

    http_response, okta_user, email = validate_user_for_otp(email)
    if http_response or not okta_user or not email:
        return http_response

    try:
        db_user = User.objects.get(email__iexact=email)

        verification_code = get_random_otp(OTP_DEFAULT_LENGTH)
        magic_link = MagicLink.objects.update_or_create(
            user=db_user, defaults={'temporary_code': verification_code}
        )[0]

        login_link = LOGIN_APP_URL.get(str(ENVIRONMENT), ORIGIN_LOCALHOST[2])
        template_context = {
            'verification_code': verification_code,
            'login_link': f'{login_link}/code?magic={magic_link.token}',
        }

        send_verification_code_email(email, template_context)
        return HttpResponse('SENT OKTA VERIFICATION CODE')
    except Exception as e:
        logger.warning(f'Error getting one time token for {email}. Trace: {e}')
        return HttpResponseServerError('Service error')


def send_verification_code_email(email: str, template_context: dict):
    send_email(
        subject='Laika Verification Code',
        from_email=NO_REPLY_EMAIL,
        to=[email],
        template='email/forgot_password.html',
        template_context=template_context,
    )


@api_key
def activate_user(request):
    username = email_validator(request.GET.get('username'))
    if not username:
        return invalid_request()

    User.objects.filter(email__iexact=username).update(
        password_expired=False, invitation_sent=timezone.now()
    )
    return JsonResponse({'success': True})


def get_days_until_today(first_date) -> int:
    return (timezone.now() - first_date).days


def get_seconds_until_today(first_date) -> float:
    return (timezone.now() - first_date).total_seconds()


def is_password_expired(user: User) -> bool:
    if not user or not user.invitation_sent:
        return False

    if (
        get_days_until_today(user.invitation_sent)
        >= PASSWORD_TIMES['PASSWORD_EXPIRATION_DAYS']
    ):
        return True

    return False


def expire_user_password(user: User):
    user.password_expired = True
    user.save()


def is_sso(user_domain: str) -> bool:
    try:
        domain = IdentityProviderDomain.objects.get(domain=user_domain)
        sso = IdentityProvider.objects.get(id=domain.idp_id)
        if sso and sso.state == DONE_ENABLED:
            logger.info(
                f'Returning OKTA for allowed default domains, selected: {domain}'
            )
            return True
        return False
    except Exception as e:
        logger.warning(f'Error found when getting user sso: {e}')
        return False


@api_key
def get_user_status(request):
    username = email_validator(request.GET.get('username'))
    user = User.objects.get(email__iexact=username)
    status = calculate_user_status(user)

    return JsonResponse({'status': status})


@api_key
def get_user_idp(request):
    username = request.GET.get('username')
    username = email_validator(username)

    if not username:
        return invalid_request()

    if '@heylaika' in username:
        tokens = username.split('@')
        prefixes = tokens[0].split('+')
        if len(prefixes) == 1:
            return HttpResponse(
                'Username is not found. This type of user is not allowed. '
                'Please contact an administrator.'
            )

    tokens = username.split('@')
    if is_sso(tokens[DOMAIN_INDEX]):
        return JsonResponse({'idp': 'OKTA', 'expired': False})

    try:
        logger.info(f'❗️ Getting User from: {username}')

        okta_user = OktaApi.get_user_by_email(username)
        if okta_user:
            expired = False
            db_user = User.objects.filter(email__iexact=username).first()

            if is_password_expired(db_user):
                expire_user_password(db_user)

            if db_user and db_user.password_expired:
                expired = OktaApi.expire_password(okta_user.id)

            logger.info('User to login using OKTA')
            return JsonResponse({'idp': 'OKTA', 'expired': expired})

        elif cognito.get_user(username):
            logger.info('User to login using COGNITO')
            return JsonResponse({'idp': 'COGNITO', 'expired': False})

        return HttpResponse(
            'Username is not found in any directory provider. '
            'Please contact an administrator.'
        )

    except Exception as e:
        logger.exception(f'Error trying to validate email: {e}')
        raise ServiceException(f'Error trying to validate email: {e}')


@api_key
@csrf_exempt
@require_POST
def get_magic_link(request: HttpRequest, token: str):
    try:
        email, password = MagicLink.objects.get(token=token).temporary_credentials
        if email and not password:
            expored_invite_user = User.objects.get(email=email)
            logger.warning(f'Magic link for {expored_invite_user.id} has expired')
            return HttpResponse(MAGIC_LINK_TOKEN_EXPIRED, status=403)
        if not email or not password:
            logger.warning('Magic link not found')
            return HttpResponse('Not Found', status=404)
        return HttpResponse(f'{email}:{password}')
    except MagicLink.DoesNotExist as e:
        logger.warning(e)
        return HttpResponseNotFound(MAGIC_LINK_NOT_FOUND)
    except Exception as e:
        logger.warning(e)
        return HttpResponseServerError('Fatal error')


@api_key
@csrf_exempt
@require_POST
def get_otp_from_magic_link(request: HttpRequest):
    body_obj = json.loads(request.body.decode('utf-8'))
    token = body_obj.get('token')

    if not token:
        return invalid_request()

    try:
        email, otp = MagicLink.objects.get(token=token).otp_credentials
        if email and not otp:
            return HttpResponseForbidden('Token expired')
        if not email and not otp:
            return HttpResponseNotFound(MAGIC_LINK_NOT_FOUND)
        return HttpResponse(f'{email}:{otp}')
    except MagicLink.DoesNotExist as e:
        logger.warning(e)
        return HttpResponseNotFound(MAGIC_LINK_NOT_FOUND)
    except Exception as e:
        logger.warning(e)
        return HttpResponseServerError('Fatal error')


class MigratePolarisUsersView(LoginRequiredMixin, FormView):
    form_class = MigratePolarisUsersForm
    template_name = 'admin/migrate_polaris_users.html'
    success_url = '/admin/user/user'
    login_url = '/admin/login/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Upload CSV File'
        context['name'] = 'User'
        context['has_permission'] = True
        context['has_add_permission'] = True
        context['has_change_permission'] = True
        context['is_popup'] = False
        context['available_apps'] = admin.site.get_app_list(self.request)
        context['is_nav_sidebar_enabled'] = True

        return context
